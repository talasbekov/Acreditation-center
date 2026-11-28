import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { LangProvider } from "@/lib/i18n";
import { ToastProvider } from "@/components/toast";

export const metadata: Metadata = {
  title: "Центр аккредитации",
  description: "Система аккредитации для режимных мероприятий (СГО РК)",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>
        <LangProvider>
          <AuthProvider>
            <ToastProvider>{children}</ToastProvider>
          </AuthProvider>
        </LangProvider>
      </body>
    </html>
  );
}
