# Como publicar o Data Detectives no GitHub Pages

Tempo: cerca de 10 minutos. Precisa de: uma conta no GitHub e o arquivo `data-detectives-site.zip`.
Não precisa instalar nada nem usar terminal. Tudo é feito pelo navegador.

No final você terá um link público, assim: `https://SEU-USUARIO.github.io/data-detectives/`

---

## 1. Descompactar o pacote

1. Descompacte `data-detectives-site.zip`.
2. Abra a pasta `data-detectives` que aparece. Dentro dela devem estar:

```
index.html     app.js     i18n.js     style.css
README.md      TUTORIAL-GITHUB-PAGES.md
assets/        (logo.webp)
data/          (catalog.json, enso.json, models.json)
scripts/       (arquivos .py)
```

Se faltar a pasta `data`, o site abre vazio. Peça o pacote de novo.

## 2. Entrar no GitHub

Acesse https://github.com e faça login. Se não tiver conta, clique em **Sign up** (é gratuito).

## 3. Criar o repositório

1. Acesse https://github.com/new
2. Em **Repository name**, escreva: `data-detectives`
3. Marque **Public**. O GitHub Pages gratuito só funciona com repositório público.
4. **Não** marque "Add a README file", nem `.gitignore`, nem licença.
5. Clique em **Create repository**.

## 4. Enviar os arquivos

1. Na página do repositório recém-criado, clique no link **uploading an existing file**
   (ele aparece na frase "…or create a new file or upload an existing file").
2. Abra a pasta `data-detectives` no seu computador e selecione **tudo o que está dentro dela** (Ctrl+A, ou Cmd+A no Mac).
3. Arraste a seleção para a área de upload do GitHub.
   - Arraste o **conteúdo** da pasta, não a pasta `data-detectives` em si.
   - Use Chrome, Edge ou Firefox. Eles mantêm as subpastas `data/`, `assets/` e `scripts/`.
4. Espere a lista terminar de carregar. Confira se aparecem `data/catalog.json`, `data/models.json`, `data/enso.json` e `assets/logo.webp`.
5. Embaixo, em "Commit changes", deixe a mensagem padrão e clique em **Commit changes**.

**Conferência:** na página principal do repositório, o arquivo `index.html` deve aparecer direto na lista, ao lado das pastas `assets`, `data` e `scripts`.
Se em vez disso aparecer só uma pasta `data-detectives`, os arquivos subiram um nível abaixo. Apague o repositório (Settings → Danger Zone → Delete) e repita o passo 4 arrastando o **conteúdo** da pasta.

## 5. Ligar o GitHub Pages

1. No repositório, clique em **Settings** (aba no topo, à direita).
2. No menu da esquerda, clique em **Pages**.
3. Em **Build and deployment**:
   - **Source:** `Deploy from a branch`
   - **Branch:** `main` e pasta `/ (root)`
4. Clique em **Save**.

## 6. Esperar e pegar o link

1. Espere de 1 a 3 minutos.
2. Na aba **Actions** do repositório aparece "pages build and deployment". Quando ficar com um ✓ verde, está pronto.
3. Volte em **Settings → Pages**. No topo aparece **"Your site is live at …"** com o link.

O link é: `https://SEU-USUARIO.github.io/data-detectives/`

## 7. Testar o site

Abra o link e confira:

- [ ] A página abre com o globo girando e a logo no canto superior esquerdo.
- [ ] Depois de alguns segundos, a seção 1 mostra **Petrópolis** com o texto "NASA POWER até …" (os dados da NASA carregaram).
- [ ] Buscar outra cidade (ex.: `Medellín`) mostra os gráficos daquele lugar.
- [ ] Os botões **PT / EN / ES** trocam o idioma.
- [ ] No globo, a camada **Chuva (IMERG)** mostra a chuva de ontem.

Depois, envie o link para quem pediu a publicação.

---

## Se algo der errado

| Problema | Causa provável | O que fazer |
|---|---|---|
| Página 404 do GitHub | O Pages ainda está publicando, ou a branch/pasta está errada | Espere 3 minutos e recarregue. Confira o passo 5 (`main` e `/ (root)`). |
| 404 e o repositório mostra uma pasta `data-detectives` | Os arquivos subiram dentro de uma pasta | Refaça o passo 4 arrastando o **conteúdo** da pasta. |
| Página abre, mas aparece "Falha ao iniciar o app" | A pasta `data/` não foi enviada | Envie a pasta `data` com os três arquivos `.json` (Add file → Upload files). |
| Aparece "A NASA POWER não respondeu" | A API da NASA limitou os pedidos | Espere alguns segundos e clique em **Tentar de novo**. Não é erro da publicação. |
| Página antiga depois de atualizar | Cache do navegador | Recarregue com Ctrl+Shift+R. |

## Como atualizar depois

1. No repositório, clique em **Add file → Upload files**.
2. Arraste os arquivos que mudaram, mantendo as mesmas pastas.
3. Clique em **Commit changes**. O GitHub Pages republica sozinho em 1 a 3 minutos.
