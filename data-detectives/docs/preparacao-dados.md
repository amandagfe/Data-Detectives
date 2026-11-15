# Segurança, rastreabilidade e preparação dos dados

Estado verificado em 15/11/2026. Esta etapa não treinou, substituiu ou promoveu modelos. Os artefatos atuais em `data/models.json` permanecem inalterados.

## Resultado executivo

| Frente | Resultado comprovado | Limitação/pêndencia |
|---|---|---|
| Telegram | backend opcional implementado; token e destinatário ficam no ambiente do servidor e não chegam ao navegador | token compartilhado fora do secret manager deve ser tratado como exposto; rate limit em memória precisa de camada distribuída se houver múltiplas instâncias |
| GLC | bruto imutável, manifesto e catálogo v2 preservam 11.033 IDs, coordenadas, precisão, nulidade e origem | licença continua “não especificada” no portal; isso não autoriza inferir condições de reutilização |
| COOLR | Reports Points integrado ao mapa/histórico por `event_id`, com 14.753 IDs únicos | versão e licença explícita não constam dos metadados auditados; modelos continuam até 2017 |
| POWER | ledger novo reconcilia 8.197 candidatos; piloto de três células validou quatro candidatos | 7.953 pares continuam pendentes; a perda histórica DD-027 continua inexplicável sem os intermediários originais |
| tempo | regra preditiva D−1 explícita e quatro testes de fronteira passaram | datas do GLC não têm fuso confiável; a regra é conservadora, não uma reconstrução da hora real de cada evento |
| estrutural | grade independente dos eventos, cortes espaciais/temporais e conjunto de teste reservado foram preparados | 51 registros ficam fora do domínio cartográfico independente; a política para ilhas/coordenadas costeiras precisa ser decidida antes do treino final |
| GIBS | `TIME`, data representada e fallback são carregados de `data/gibs.json` e exibidos | metadados são um snapshot de 15/11/2026 e precisam ser atualizados offline; uma resposta de imagem não valida o valor científico do pixel |

## 1. Segurança do Telegram

### Verificações

- Busca por formato de token em todos os arquivos atuais: nenhum candidato nos arquivos de aplicação. Um único texto com formato semelhante apareceu em `photo_link` do CSV bruto e do snapshot COOLR; o host é `cdn01.allafrica.com`, não Telegram, e o valor não é reproduzido aqui.
- Busca pelo mesmo padrão em todos os objetos do único commit existente: zero candidatos.
- Busca por `api.telegram.org`, `DD_TELEGRAM`, `telegram.config` e `localStorage['dd-tg']` em `index.html`, `app.js`, `i18n.js` e `style.css`: zero resultados.
- `server.py` reintroduz o botão e o envio por backend. O cliente consulta somente o estado e envia payload fixo; segredo e `chat_id` não aparecem nas respostas. O token fornecido na conversa desta etapa não foi gravado ou executado.

Esses testes comprovam apenas o repositório e o diretório atual. Eles não inspecionam caches, forks, logs ou artefatos de hospedagem externos.

### Ação de incidente, se houve publicação anterior

Qualquer token entregue a navegador, conversa ou log deve ser tratado como exposto. O backend aceita credenciais por ambiente, mas isso não desfaz exposição anterior. A ação recomendada continua sendo `/revoke` no BotFather, seguida de novo token configurado diretamente no ambiente/secret manager. Sem `TELEGRAM_ALERTS_ENABLED`, token e destino, o envio permanece desativado.

## 2. Catálogo local preservado

O bruto está em `data/sources/glc/2026-11-15/Global_Landslide_Catalog_Export_rows.csv`, modo `0444`. O manifesto registra URL de origem, recurso, obtenção UTC, tamanho, período dos eventos e SHA-256 `2c4898899dd4f373c4320e121c5b655ebb5394d431fa42e57ec4828d07d48b04`.

`scripts/build_catalog.py` verifica o hash e produz `data/catalog.json` schema v2 por escrita atômica. A reprodução feita por `scripts/audit_data.py --raw-glc ... --strict` comparou, na ordem da fonte, ID, linha, data, coordenadas exatas, precisão, fatalidade nula e referências: 11.033/11.033 corresponderam e não houve problema estrutural.

| Propriedade | Antes | Agora |
|---|---|---|
| identidade | ausente | `event_id` e `source_row` |
| coordenadas | arredondadas a 0,01° | valor decimal da fonte |
| precisão | descartada | `location_accuracy`; dois ausentes preservados |
| fatalidades | vazio convertido em zero | 1.385 ausentes distintos de zero observado |
| origem | descartada | nome, URL, foto e IDs de importação |
| duplicidade | 135 representações compactas excedentes indistinguíveis | zero IDs duplicados; 41 linhas extras compartilham coordenada/data, mas permanecem registros distintos |

O consumidor `app.js` aceita o schema v2 e ainda usa zero apenas para somas visuais quando a contagem é ausente, mantendo `fatKnown` e exibindo quantos registros não informam fatalidade no total global e no raio consultado. A contagem de registros e o mapa continuam com 11.033 itens. Nenhum evento foi deduplicado por coincidência espacial/temporal. O JSON público passou de 466.108 bytes para 5.657.879 bytes; descrições extensas permanecem somente no CSV bruto, referenciadas por `source_row`, para limitar o custo de carregamento sem perder o original.

## 3. COOLR atual

A página oficial do COOLR distingue dados baseados em relatos (GLC, Landslide Reporter Catalog e contribuições) de inventários baseados em eventos. A auditoria consultou os quatro serviços oficiais ArcGIS em EPSG:4326:

| Componente | Contagem no acesso | Snapshot local |
|---|---:|---|
| Reports Points | 14.750 | oito páginas brutas, hashes no manifesto |
| Reports Polygons | 48 | apenas metadados/contagem |
| Events Points | 40.154 | apenas metadados/contagem |
| Events Polygons | 22.421 | apenas metadados/contagem |

O GLC local continua com período 1988-11-07 a 2017-09-28. Isso não é a cobertura de todo o COOLR. No snapshot Reports Points, 13.113/14.750 registros têm data e o intervalo informado é 1915-12-15 a 2025-05-18; 27 coordenadas estão ausentes/inválidas. O bruto preserva os 14.750 registros, sem descarte. Entre os IDs, 11.030 são comuns ao arquivo local, 3.720 aparecem somente no snapshot atual e três somente no local. Nos IDs comuns, 718 coordenadas, 28 precisões, 44 nomes de fonte e quatro datas diferem. Essas diferenças podem representar edição/correção/versionamento; não são automaticamente erros. Os metadados auditados não forneceram versão semântica nem licença explícita de reutilização; ambas permanecem não verificadas e devem ser resolvidas antes de redistribuir/integrar.

Após decisão explícita do responsável, `scripts/integrate_coolr_catalog.py` aplicou a seguinte política: COOLR substitui a linha local quando o mesmo `event_id` existe; IDs exclusivos das duas fontes são mantidos; proximidade/data nunca deduplicam. A execução verificou os oito hashes e gerou 14.753 IDs únicos: 11.030 substituídos, 3.720 adicionados e três preservados. Há 13.116 datas válidas, 14.726 coordenadas válidas, 1.637 datas ausentes e 27 coordenadas ausentes/inválidas. O mapa/histórico mudou; `data/models.json` não foi alterado.

## 4. Nova execução meteorológica

`scripts/weather_pipeline.py` usa SQLite como ledger e cache por célula. `prepare`, `collect` e `reconcile` são comandos separados do site. Cada tentativa registra célula, início/fim, URL, resultado, erro e hash; cada candidato registra ID estável, evento(s), gatilho(s), coleta, produto, versão da API, referência temporal, validação, exclusão e tentativas.

Reconciliação inicial:

| Quantidade | Valor | Significado |
|---|---:|---|
| registros GLC 2007–2017 com precisão aceita | 9.611 | linhas antes do agrupamento |
| células antes do filtro de gatilho | 2.567 | significado confirmado do número anteriormente chamado de “lugares” |
| pares célula-data | 8.197 | candidatos rastreáveis |
| excluídos | 240 | todos os registros vinculados têm gatilho explicitamente não meteorológico |
| pendentes após preparo | 7.957 | candidatos que exigem POWER |
| células pendentes | 2.496 | células únicas após o filtro |

O piloto baixou três células, com uma tentativa por célula, produto `MERRA2` e API `v2.10.3`. Quatro candidatos ficaram válidos porque uma célula contém duas datas. Estado final do piloto: 4 válidos + 240 excluídos + 7.953 pendentes = 8.197, zero perda silenciosa. O ledger/cache está em `data/runs/weather/2026-11-15-v1/` e é artefato de trabalho ignorado pelo Git; os comandos e totais ficam documentados e são reproduzíveis.

DD-027 não foi “resolvida” por essa execução. Ela pergunta por que o treino antigo reduziu 7.957 candidatos a 5.361 casos; sem seus caches e intermediários não é possível atribuir causa retrospectiva a cada perda. O novo ledger evita repetir essa lacuna em execuções futuras.

## 5. Regra temporal

O GLC fornece uma data civil e, em muitos registros, meia-noite/meio-dia textual, mas não fornece fuso confiável para reconstruir o instante. POWER identifica as séries usadas como LST. A nova regra separa finalidades:

- análise retrospectiva pode examinar D e dados posteriores, desde que seja rotulada como retrospectiva;
- previsão para um evento de data D usa somente POWER LST até D−1;
- chuva de 30 dias cobre D−30 a D−1; `GWETTOP` e `GWETROOT` usam D−1;
- climatologias, percentis e transformações aprendidas devem terminar no corte de treino, nunca usar anos posteriores ao exemplo.

`tests/test_temporal_alignment.py` verifica 30 dias, exclusão de D, mudança de ano, ano bissexto e presença explícita de `time-standard=LST`. Quatro testes passaram. A regra reduz vazamento; não prova que D−1 corresponde ao instante físico de todos os eventos.

## 6. Pipeline estrutural sem domínio futuro

O vazamento antigo permanece confirmado em `scripts/train_structural.py`: o conjunto `has` e a vizinhança `C` usam eventos de 2007–2017 antes dos cortes. A auditoria identificou ainda:

- a delimitação dos negativos conhece células com eventos posteriores ao corte;
- `permutation_importance` usa o conjunto chamado de teste; qualquer decisão de atributos baseada nela transformaria o teste em validação;
- o ajuste final concatena treino e teste (`Xtr/Xte`, `ytr/yte`) e não preserva avaliação intocada para esse modelo final;
- os quantis finais são calculados sobre todas as saídas do domínio previsto; podem servir à visualização, mas não à seleção/avaliação;
- contagens/frações são recalculadas por janela. Elas não usam futuro dentro de `feats(y0,y1)`, mas qualquer normalizador aprendido futuro deve ser proibido explicitamente.

O candidato v2 não treina. `scripts/build_land_grid.py` deriva 29.496 células de 1° exclusivamente do contorno `land` do world-atlas: centro terrestre ou margem costeira conservadora de 2°. `scripts/prepare_structural_v2.py` cria atributos apenas até cada corte, particiona blocos espaciais de 5° de modo determinístico e reserva:

- seleção: treino 2007–2012 → 2013–2014, validação espacial e validação temporal em 2015;
- testes intocados: temporal e espacial com atributos até 2015 → rótulos 2016–2017.

Células sem histórico ficam na grade com `has_local_history=0`; fração de gatilho por chuva fica `null` com indicador de ausência, sem sentinela `-1`. Escalonadores ou qualquer transformação aprendida só podem ser ajustados no subconjunto de treino de cada corte. O smoke test materializou 600 linhas sem treinar.

Dos 10.988 registros do período, 51 caem fora da grade independente, inclusive registros classificados com precisão de 1–25 km. Isso pode refletir ilhas ausentes no mapa 110m, coordenadas costeiras ou incerteza espacial. Eles são contados no manifesto e impedem considerar o domínio definitivo.

## 7. Datas GIBS

`scripts/update_gibs_metadata.py` consulta WMS GetCapabilities e testa GetMap. Para a data desejada 14/11/2026:

| Camada | TIME enviado | Data representada verificável | Fallback |
|---|---|---|---|
| IMERG | 13/11/2026 | 13/11/2026 | sim; 14/11 não constava no capabilities |
| SMAP L4 | 10/11/2026 | 10/11/2026 | sim; 14/11 não constava no capabilities |
| VIIRS NOAA-20 | 14/11/2026 | 14/11/2026 | não |
| NDH 2000 | sem `TIME` | camada estática | não aplicável |

As quatro requisições retornaram imagens válidas na verificação. `app.js` envia o `TIME` de `data/gibs.json` e a interface mostra data desejada, fallback e data representada. “Representada” aqui significa listada no capabilities para a camada e aceita pelo GetMap; não prova atualidade local, ausência de nuvens ou correção do conteúdo.

## 8. Prontidão para treinamento

| Modelo | Dados adequados? | Pipeline adequado? | Pode iniciar treinamento de candidato? |
|---|---|---|---|
| meteorológico/disparo | **não**: somente três de 2.496 células foram coletadas no piloto | **sim para continuar a coleta**, com ledger/checkpoint/cache; protocolo futuro de split e transformações ainda deve ser acoplado ao treino | **não** |
| estrutural/recorrência | **parcial**: catálogo v2 está rastreável, mas 51 registros ficam fora do domínio proposto | **parcial**: cortes, atributos e proteção do teste existem; falta decidir/validar o domínio e materializar a execução completa | **não** |

O modelo meteorológico atual e o estrutural atual continuam publicados apenas como artefatos históricos já auditados. Nenhum resultado desta etapa deve ser interpretado como uma nova métrica ou melhoria de desempenho.
