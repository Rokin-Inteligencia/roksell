# WhatsApp Business Cloud - Envio de pedidos

Este projeto agora aceita envio do resumo do pedido por WhatsApp (como jÃ¡ acontece com Telegram) usando as variÃ¡veis de ambiente:

- `WHATSAPP_TOKEN`: token permanente de um usuÃ¡rio de sistema na sua conta Meta.
- `WHATSAPP_PHONE_NUMBER_ID`: **phone number ID** do nÃºmero do WhatsApp Business que enviarÃ¡ a mensagem.
- `WHATSAPP_WEBHOOK_VERIFY_TOKEN`: token que a Meta envia no GET de verificaÃ§Ã£o do webhook (qualquer string secreta que vocÃª definir no painel).
- `WHATSAPP_APP_SECRET`: **App Secret** do app Meta (em ConfiguraÃ§Ãµes do app > BÃ¡sico). ObrigatÃ³rio para receber eventos no POST do webhook: a API valida o header `X-Hub-Signature-256` com esse secret. Sem ele, os endpoints POST do webhook retornam 503.

Sem `WHATSAPP_TOKEN` e `WHATSAPP_PHONE_NUMBER_ID`, o envio de mensagens Ã© ignorado (nenhum erro Ã© lanÃ§ado).

## Passo a passo na Meta

1) Acesse [developers.facebook.com](https://developers.facebook.com/) com a conta do Business Manager.  
2) Crie um app do tipo **Business** e adicione o produto **WhatsApp**.  
3) Dentro do produto WhatsApp, crie um **System User** (UsuÃ¡rio de Sistema) no Business Manager, dÃª a ele permissÃ£o `whatsapp_business_messaging`.  
4) Gere um **token permanente** para esse usuÃ¡rio de sistema com escopo `whatsapp_business_messaging` (nÃ£o use o token temporÃ¡rio de 24h). Guarde esse valor em `WHATSAPP_TOKEN`.  
5) Ainda no painel do WhatsApp, copie o **Phone Number ID** do nÃºmero que vai disparar as mensagens e salve em `WHATSAPP_PHONE_NUMBER_ID`.  
6) (Opcional) Cadastre um template transacional, caso precise enviar fora da janela de 24h. Para mensagens disparadas logo apÃ³s a compra, um texto simples costuma ficar dentro da janela.  
7) No `.env` do `roksell-backend`, defina as variÃ¡veis e reinicie a API:
   ```
   WHATSAPP_TOKEN=seu_token_permanente
   WHATSAPP_PHONE_NUMBER_ID=123456789012345
   ```
8) FaÃ§a um pedido no app. A API irÃ¡:
   - montar um texto com ID do pedido, nome e telefone do cliente, endereÃ§o (ou pickup), itens, pagamento e totais;
   - enviar em background para o telefone informado no checkout, normalizado apenas para dÃ­gitos (`55DDD...`).

## Teste rÃ¡pido via curl

Substitua o token, phone number id e nÃºmero de destino (no formato internacional apenas com dÃ­gitos):

```bash
curl -X POST "https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages" \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "55DDDNNNNNNN",
    "type": "text",
    "text": { "body": "Teste de envio" }
  }'
```

## PrÃ³ximos passos (mÃ³dulo de automaÃ§Ã£o)

- Criar uma tabela/configuraÃ§Ã£o por tenant para armazenar `whatsapp_token` e `whatsapp_phone_number_id` em vez de usar variÃ¡veis de ambiente globais.  
- Expor uma aba â€œAutomaÃ§Ã£oâ€ no painel (similar ao cadastro de produtos) para cada cliente configurar seus prÃ³prios dados.  
- Validar nÃºmero e token com um endpoint de teste e salvar status (ex.: â€œoperacionalâ€, â€œtoken invÃ¡lidoâ€).  
- Opcional: suportar envio via templates aprovados e webhooks de entrega/leitura.

