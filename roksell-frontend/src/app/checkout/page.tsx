import { Suspense } from "react";
import CheckoutClient from "./CheckoutClient";

export const dynamic = "force-dynamic";

export default function CheckoutPage() {
  return (
    <Suspense fallback={<div className="p-4">Carregando...</div>}>
      <CheckoutClient />
    </Suspense>
  );
}
