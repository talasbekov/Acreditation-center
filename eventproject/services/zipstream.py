"""Потоковая сборка ZIP без временного файла и без хранения архива.

Архив складывается из заголовков и содержимого файлов прямо в ответ. Сжатие не
применяется (метод STORED): фото и сканы — JPEG, он не сжимается, а без сжатия
размер архива и смещение каждого байта известны заранее. Отсюда:

- `Content-Length` до начала передачи (клиент видит прогресс и обрыв);
- отдача произвольного диапазона байт (`Range`) — докачка после обрыва; для неё
  нужны заранее известные CRC-32 (режим «с известными CRC», пакеты выгрузки);
- память не зависит от размера архива: файлы читаются блоками.

Если CRC неизвестен (`Entry.crc is None`), он считается при отдаче и пишется в
data descriptor после содержимого; длина архива при этом тоже известна заранее,
но диапазоны не поддерживаются.

Каждый файл сверяется с ожидаемым размером и, если задан, SHA-256 / CRC. Последний
блок файла придерживается до окончания сверки: при расхождении поток обрывается
исключением `SourceChanged`, и клиент не получает полный архив с подменённым
файлом. ZIP64 включается по тем же порогам, что и в `zipfile`.
"""

import hashlib
import struct
import zlib
from dataclasses import dataclass

ZIP64_LIMIT = (1 << 31) - 1
ZIP_FILECOUNT_LIMIT = (1 << 16) - 1
CHUNK_SIZE = 1024 * 1024
_FLUSH_SIZE = 256 * 1024

_LOCAL_SIG = 0x04034B50
_CENTRAL_SIG = 0x02014B50
_DESCRIPTOR_SIG = 0x08074B50
_EOCD_SIG = 0x06054B50
_ZIP64_EOCD_SIG = 0x06064B50
_ZIP64_LOCATOR_SIG = 0x07064B50
_UNIX = 3
_EXTERNAL_ATTR = 0o644 << 16


class SourceChanged(Exception):
    """Файл элемента пропал или отличается от ожидаемого. `args[0]` — имя в архиве."""


class RangeNotSatisfiable(ValueError):
    """Запрошенный диапазон вне архива."""


@dataclass(frozen=True)
class Entry:
    name: str
    size: int
    crc: int | None = None
    sha256: str | None = None
    data: bytes | None = None
    path: str | None = None

    @property
    def zip64(self):
        return self.size > ZIP64_LIMIT

    @property
    def flags(self):
        flags = 0x08 if self.crc is None else 0
        if not self.name.isascii():
            flags |= 0x800
        return flags

    @property
    def version(self):
        return 45 if self.zip64 else 20


def _dos_stamp(date_time):
    year, month, day, hour, minute, second = date_time
    return (hour << 11) | (minute << 5) | (second // 2), ((year - 1980) << 9) | (month << 5) | day


def _local_header(entry, stamp):
    name = entry.name.encode("utf-8")
    if entry.zip64:
        sizes, extra = (0xFFFFFFFF, 0xFFFFFFFF), struct.pack("<HHQQ", 1, 16, entry.size, entry.size)
    else:
        sizes, extra = (entry.size, entry.size), b""
    return struct.pack(
        "<IHHHHHIIIHH", _LOCAL_SIG, entry.version, entry.flags, 0, stamp[0], stamp[1],
        entry.crc or 0, sizes[0], sizes[1], len(name), len(extra),
    ) + name + extra


def _descriptor(entry, crc):
    if entry.zip64:
        return struct.pack("<IIQQ", _DESCRIPTOR_SIG, crc, entry.size, entry.size)
    return struct.pack("<IIII", _DESCRIPTOR_SIG, crc, entry.size, entry.size)


def _descriptor_size(entry):
    if entry.crc is not None:
        return 0
    return 24 if entry.zip64 else 16


def _central_record(entry, crc, offset, stamp):
    name = entry.name.encode("utf-8")
    fields = []
    size_field = entry.size
    if entry.zip64:
        fields += [entry.size, entry.size]
        size_field = 0xFFFFFFFF
    offset_field = offset
    if offset > ZIP64_LIMIT:
        fields.append(offset)
        offset_field = 0xFFFFFFFF
    extra = struct.pack(f"<HH{len(fields)}Q", 1, 8 * len(fields), *fields) if fields else b""
    version = 45 if fields else 20
    return struct.pack(
        "<IHHHHHHIIIHHHHHII", _CENTRAL_SIG, (_UNIX << 8) | version, version, entry.flags, 0,
        stamp[0], stamp[1], crc, size_field, size_field, len(name), len(extra), 0, 0, 0,
        _EXTERNAL_ATTR, offset_field,
    ) + name + extra


def _central_record_size(entry, offset):
    fields = (2 if entry.zip64 else 0) + (1 if offset > ZIP64_LIMIT else 0)
    return 46 + len(entry.name.encode("utf-8")) + (4 + 8 * fields if fields else 0)


def _end_records(count, cd_offset, cd_size):
    tail = b""
    if count > ZIP_FILECOUNT_LIMIT or cd_offset > ZIP64_LIMIT or cd_size > ZIP64_LIMIT:
        zip64_offset = cd_offset + cd_size
        tail += struct.pack(
            "<IQHHIIQQQQ", _ZIP64_EOCD_SIG, 44, (_UNIX << 8) | 45, 45, 0, 0, count, count, cd_size, cd_offset,
        )
        tail += struct.pack("<IIQI", _ZIP64_LOCATOR_SIG, 0, zip64_offset, 1)
    tail += struct.pack(
        "<IHHHHIIH", _EOCD_SIG, 0, 0, min(count, ZIP_FILECOUNT_LIMIT), min(count, ZIP_FILECOUNT_LIMIT),
        min(cd_size, 0xFFFFFFFF), min(cd_offset, 0xFFFFFFFF), 0,
    )
    return tail


def _end_records_size(count, cd_offset, cd_size):
    return len(_end_records(count, cd_offset, cd_size))


class ZipStream:
    """Детерминированный ZIP из `entries` с меткой времени `date_time` (кортеж UTC)."""

    def __init__(self, entries, date_time):
        names = [entry.name for entry in entries]
        if len(set(names)) != len(names):
            raise ValueError("duplicate archive names")
        for entry in entries:
            if entry.data is not None and len(entry.data) != entry.size:
                raise ValueError(f"size mismatch for {entry.name}")
        self.entries = list(entries)
        self.stamp = _dos_stamp(date_time)
        self.ranges_supported = all(entry.crc is not None for entry in self.entries)

        # Сегменты: (смещение, длина, вид, элемент). Вид: header / data / descriptor / central.
        self._segments = []
        self._offsets = []
        position = 0
        for entry in self.entries:
            self._offsets.append(position)
            header = _local_header(entry, self.stamp)
            self._segments.append((position, len(header), "header", entry))
            position += len(header)
            self._segments.append((position, entry.size, "data", entry))
            position += entry.size
            descriptor = _descriptor_size(entry)
            if descriptor:
                self._segments.append((position, descriptor, "descriptor", entry))
                position += descriptor
        self._cd_offset = position
        self._cd_size = sum(
            _central_record_size(entry, offset) for entry, offset in zip(self.entries, self._offsets)
        )
        central = self._cd_size + _end_records_size(len(self.entries), self._cd_offset, self._cd_size)
        self._segments.append((position, central, "central", None))
        self.size = position + central

    # --- отдача ---------------------------------------------------------------

    def iter_bytes(self, start=0, end=None):
        """Байты архива в полуинтервале [start, end). По умолчанию — весь архив."""
        end = self.size if end is None else end
        if not 0 <= start <= end <= self.size:
            raise RangeNotSatisfiable((start, end))
        if (start, end) != (0, self.size) and not self.ranges_supported:
            raise RangeNotSatisfiable("ranges need known CRC values")

        crcs = {}
        buffer = bytearray()
        for seg_start, seg_len, kind, entry in self._segments:
            seg_end = seg_start + seg_len
            if seg_end <= start or seg_start >= end:
                continue
            lo, hi = max(start, seg_start) - seg_start, min(end, seg_end) - seg_start
            if kind == "data":
                holder = {}
                for piece in self._entry_pieces(entry, lo, hi, holder):
                    buffer += piece
                    if len(buffer) >= _FLUSH_SIZE:
                        yield bytes(buffer)
                        buffer.clear()
                crcs[entry.name] = holder["crc"]
                continue
            if kind == "header":
                blob = _local_header(entry, self.stamp)
            elif kind == "descriptor":
                blob = _descriptor(entry, crcs[entry.name])
            else:
                blob = self._central_blob(crcs)
            buffer += blob[lo:hi]
            if len(buffer) >= _FLUSH_SIZE:
                yield bytes(buffer)
                buffer.clear()
        if buffer:
            yield bytes(buffer)

    def _central_blob(self, crcs):
        records = b"".join(
            _central_record(entry, entry.crc if entry.crc is not None else crcs[entry.name], offset, self.stamp)
            for entry, offset in zip(self.entries, self._offsets)
        )
        return records + _end_records(len(self.entries), self._cd_offset, len(records))

    def _entry_pieces(self, entry, lo, hi, holder):
        """Срез [lo, hi) содержимого элемента; файл читается и сверяется целиком."""
        if entry.data is not None:
            data = entry.data
            crc = zlib.crc32(data)
            if not self._matches(entry, len(data), crc, hashlib.sha256(data).hexdigest() if entry.sha256 else None):
                raise SourceChanged(entry.name)
            holder["crc"] = crc
            if lo < hi:
                yield data[lo:hi]
            return

        digest = hashlib.sha256() if entry.sha256 else None
        crc = 0
        position = 0
        pending = None
        try:
            source = open(entry.path, "rb")
        except OSError as exc:
            raise SourceChanged(entry.name) from exc
        with source:
            while True:
                chunk = source.read(CHUNK_SIZE)
                if not chunk:
                    break
                if digest is not None:
                    digest.update(chunk)
                crc = zlib.crc32(chunk, crc)
                chunk_start, position = position, position + len(chunk)
                if position > entry.size:
                    raise SourceChanged(entry.name)
                cut_lo, cut_hi = max(lo, chunk_start), min(hi, position)
                if cut_lo < cut_hi:
                    if pending is not None:
                        yield pending
                    pending = chunk[cut_lo - chunk_start:cut_hi - chunk_start]
        if not self._matches(entry, position, crc, digest.hexdigest() if digest else None):
            raise SourceChanged(entry.name)
        holder["crc"] = crc
        if pending is not None:
            yield pending

    @staticmethod
    def _matches(entry, size, crc, sha256):
        if size != entry.size:
            return False
        if entry.crc is not None and crc != entry.crc:
            return False
        return entry.sha256 is None or sha256 == entry.sha256


def describe_file(path):
    """(размер, CRC-32, SHA-256) файла за одно чтение блоками."""
    digest = hashlib.sha256()
    crc = 0
    size = 0
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(chunk)
            crc = zlib.crc32(chunk, crc)
            size += len(chunk)
    return size, crc, digest.hexdigest()


def parse_range(header, size):
    """`Range: bytes=a-b` → (start, end) полуинтервал; None — отдать целиком.

    Поддерживается один диапазон. Несколько диапазонов или нераспознанная форма
    → None (полный ответ 200, как разрешает RFC 9110). Вне архива →
    RangeNotSatisfiable (416).
    """
    if not header:
        return None
    unit, _, spec = header.partition("=")
    if unit.strip().lower() != "bytes" or "," in spec:
        return None
    first, _, last = spec.strip().partition("-")
    try:
        if first == "":
            suffix, start, stop = int(last), None, None
        else:
            suffix, start, stop = None, int(first), int(last) + 1 if last else size
    except ValueError:
        return None
    if suffix is not None:
        if suffix <= 0:
            raise RangeNotSatisfiable(header)
        return max(size - suffix, 0), size
    if start >= size:
        raise RangeNotSatisfiable(header)
    if stop <= start:
        return None  # last < first: недопустимый диапазон, RFC 9110 велит его игнорировать
    return start, min(stop, size)
