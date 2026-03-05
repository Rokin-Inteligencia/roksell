"use client";

/**
 * Campo de preço em reais com preenchimento a partir dos centavos.
 * O valor digitado entra da direita para a esquerda: ex. "50" = R$ 0,50; "1050" = R$ 10,50.
 */
export function PriceInput({
  valueCents,
  onChange,
  className = "",
  disabled = false,
  id,
  "aria-label": ariaLabel,
}: {
  valueCents: number;
  onChange: (cents: number) => void;
  className?: string;
  disabled?: boolean;
  id?: string;
  "aria-label"?: string;
}) {
  const displayValue =
    typeof valueCents === "number" && Number.isFinite(valueCents)
      ? (valueCents / 100).toLocaleString("pt-BR", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })
      : "";

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(/\D/g, "");
    if (raw === "") {
      onChange(0);
      return;
    }
    const maxDigits = 10;
    const truncated = raw.slice(-maxDigits);
    const cents = parseInt(truncated, 10);
    if (Number.isFinite(cents)) {
      onChange(cents);
    }
  }

  return (
    <input
      type="text"
      inputMode="decimal"
      className={className}
      value={displayValue}
      onChange={handleChange}
      disabled={disabled}
      id={id}
      aria-label={ariaLabel}
    />
  );
}
