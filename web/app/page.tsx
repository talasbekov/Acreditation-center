"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { session, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    router.replace(session ? "/events" : "/login");
  }, [ready, session, router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-slate-400">
      Загрузка…
    </div>
  );
}
