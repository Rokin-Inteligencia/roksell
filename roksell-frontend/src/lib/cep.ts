export async function viaCEP(cep: string){
  const clean = cep.replace(/\D/g,''); if (clean.length!==8) return null;
  const r = await fetch(`https://viacep.com.br/ws/${clean}/json/`);
  const j = await r.json(); if (j.erro) return null;
  return { logradouro:j.logradouro||'', bairro:j.bairro||'', cidade:j.localidade||'', uf:j.uf||'' };
}
