export default function Home() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#efe8ff_0%,#f6f4ff_35%,#f9f7ff_70%)] text-slate-900">
      <div className="relative overflow-hidden">
        <div className="absolute -top-40 right-[-10%] h-[420px] w-[420px] rounded-full bg-[#6320ee]/20 blur-3xl" />
        <div className="absolute -bottom-40 left-[-10%] h-[420px] w-[420px] rounded-full bg-[#a855f7]/15 blur-3xl" />

        <div className="relative max-w-6xl w-full mx-auto px-6 py-16 space-y-16">
          <header className="flex flex-wrap items-center justify-between gap-6">
            <div className="space-y-3">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Rokin</p>
              <h1 className="text-4xl md:text-5xl font-['Anta'] text-[#6320ee]">
                Roksell
              </h1>
              <p className="text-base md:text-lg text-slate-600 max-w-2xl">
                Seu produto merece palco. Nós entregamos a experiência que vende por você.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <a
                href="/portal"
                className="px-5 py-3 rounded-full bg-[#6320ee] text-white text-sm font-semibold shadow-lg shadow-[#6320ee]/30 hover:brightness-95 transition"
              >
                Entrar no portal
              </a>
              <a
                href="/admin"
                className="px-4 py-3 rounded-full border border-slate-200 bg-white text-slate-700 text-sm font-semibold hover:bg-slate-100 transition"
              >
                Área admin
              </a>
            </div>
          </header>

          <section className="grid lg:grid-cols-[1.2fr_0.8fr] gap-8 items-center">
            <div className="space-y-6">
              <div className="rounded-3xl bg-white border border-slate-200 shadow-xl shadow-slate-200/60 p-8 space-y-4 opacity-0 animate-[fade-up_0.8s_ease_forwards]">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Soluções</p>
                <h2 className="text-2xl font-semibold">Tudo para sua marca vender em escala</h2>
                <p className="text-sm text-slate-600">
                  Vitrine, pedidos e relacionamento em um único fluxo para acelerar a conversão.
                  Campanhas, automação e cadastro inteligente de produtos com visão de resultado.
                </p>
                <div className="grid sm:grid-cols-2 gap-3 text-sm">
                  {[
                    "Vitrine de alta conversão",
                    "Checkout rápido e seguro",
                    "Campanhas e cupons inteligentes",
                    "Relatórios e insights",
                  ].map((item) => (
                    <div key={item} className="rounded-2xl bg-slate-50 border border-slate-200 px-4 py-3">
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-3xl bg-[#6320ee] text-white p-6 shadow-xl shadow-[#6320ee]/30 opacity-0 animate-[fade-up_0.8s_ease_forwards]" style={{ animationDelay: "120ms" }}>
                <p className="text-xs uppercase tracking-[0.2em] text-white/70">Produto Rokin</p>
                <h3 className="text-2xl font-semibold">Portal inteligente</h3>
                <p className="text-sm text-white/80">
                  Tudo na sua mão, em um só lugar: catálogo, usuários, lojas e operação.
                </p>
                <div className="mt-4 flex items-center gap-2">
                  <span className="text-xs px-3 py-1 rounded-full bg-white/15">Seguro</span>
                  <span className="text-xs px-3 py-1 rounded-full bg-white/15">Escalável</span>
                </div>
              </div>

              <div className="rounded-3xl bg-white border border-slate-200 p-6 shadow-lg shadow-slate-200/60 opacity-0 animate-[fade-up_0.8s_ease_forwards]" style={{ animationDelay: "220ms" }}>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Produtos</p>
                <h3 className="text-2xl font-semibold">Experiência que vende!</h3>
                <p className="text-sm text-slate-600">
                  Imagens, vídeos e personalização para elevar o ticket médio e fidelizar clientes.
                </p>
              </div>
            </div>
          </section>

          <section className="grid md:grid-cols-3 gap-4">
            {[
              {
                title: "Conversão",
                text: "Fluxo rápido com carrinho fluido e checkout que reduz abandono.",
              },
              {
                title: "Operação",
                text: "Equipe no controle de tudo, com eficiência e visão centralizada.",
              },
              {
                title: "Marca",
                text: "Experiência premium que transmite confiança e aumenta recorrência.",
              },
            ].map((card, index) => (
              <div
                key={card.title}
                className="rounded-2xl bg-white border border-slate-200 p-5 shadow-md shadow-slate-200/50 opacity-0 animate-[fade-up_0.8s_ease_forwards]"
                style={{ animationDelay: `${index * 120 + 180}ms` }}
              >
                <h4 className="text-lg font-semibold">{card.title}</h4>
                <p className="text-sm text-slate-600 mt-2">{card.text}</p>
              </div>
            ))}
          </section>

          <footer className="flex flex-wrap items-center justify-between gap-4 text-xs text-slate-500">
            <span>Rokin Commerce · 2026</span>
            <div className="flex items-center gap-4">
              <a href="/portal" className="hover:text-slate-700">Portal</a>
              <a href="/admin" className="hover:text-slate-700">Admin</a>
            </div>
          </footer>
        </div>
      </div>
    </main>
  );
}
