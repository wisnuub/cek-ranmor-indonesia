import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cek Ranmor Indonesia — Cek Pajak Kendaraan Seluruh Indonesia",
  description:
    "Cek pajak kendaraan bermotor, info STNK, dan data kendaraan dari seluruh provinsi di Indonesia dalam satu tempat. Gratis, cepat, mudah.",
  keywords: [
    "cek pajak kendaraan", "cek ranmor", "samsat online", "cek stnk",
    "pajak motor", "pajak mobil", "cek plat nomor", "e-samsat",
  ],
  openGraph: {
    title: "Cek Ranmor Indonesia",
    description: "Cek pajak kendaraan seluruh Indonesia",
    url: "https://ranmor.fortunamj.com",
    siteName: "Cek Ranmor Indonesia",
    locale: "id_ID",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Cek Ranmor Indonesia",
    description: "Cek pajak kendaraan seluruh Indonesia dalam satu tempat",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#DC2626",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
