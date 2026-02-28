"use client";

import React, { useState, useEffect } from 'react';

interface CurrencyInputProps {
  value: number | string;
  onChange: (value: number | string) => void;
  placeholder?: string;
  className?: string;
}

export function CurrencyInput({ value, onChange, placeholder, className }: CurrencyInputProps) {
  const [displayValue, setDisplayValue] = useState('');

  useEffect(() => {
    if (value) {
      const numberValue = Number(value) / 100;
      setDisplayValue(
        numberValue.toLocaleString('pt-BR', {
          style: 'currency',
          currency: 'BRL',
        })
      );
    } else {
      setDisplayValue('');
    }
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const inputValue = e.target.value;
    const numericValue = inputValue.replace(/\D/g, '');

    if (numericValue) {
      const numberValue = parseInt(numericValue, 10);
      onChange(numberValue);
    } else {
      onChange('');
    }
  };

  return (
    <input
      type="text"
      inputMode="decimal"
      value={displayValue}
      onChange={handleChange}
      placeholder={placeholder}
      className={className}
    />
  );
}
