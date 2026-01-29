import type { Metadata } from "next";
import { TermsContent } from "@/app/(landing)/terms/content";

export const metadata: Metadata = {
  title: "Terms of Service - Clarent Email Management",
  description: "Terms of Service - Clarent Email Management",
  alternates: { canonical: "/terms" },
};

export default function Page() {
  return <TermsContent />;
}
