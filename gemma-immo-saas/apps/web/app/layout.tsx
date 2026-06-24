import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gemma Immo",
  description: "Recherche d'opportunites immobilieres avec decote et rendement."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}

