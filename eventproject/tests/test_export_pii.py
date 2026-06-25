"""P1-9 — PII-архив экспорта не должен оставаться доступным по имени на хосте.

`_open_and_unlink` открывает файл для чтения и сразу удаляет путь: расшифрованный
ИИН+сканы в ZIP больше не лежат под именем в `/tmp` во время стрима (Linux держит
inode живым до закрытия fd).
"""

import os
import tempfile

from django.test import SimpleTestCase

from eventproject.views.export import _open_and_unlink


class OpenAndUnlinkTests(SimpleTestCase):
    def test_removes_path_but_keeps_readable(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"PII-ZIP")
        tmp.close()
        handle = _open_and_unlink(tmp.name)
        try:
            # Имени на диске больше нет (PII не доступен по пути во время стрима)…
            self.assertFalse(os.path.exists(tmp.name))
            # …но содержимое всё ещё читается из открытого дескриптора.
            self.assertEqual(handle.read(), b"PII-ZIP")
        finally:
            handle.close()
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
