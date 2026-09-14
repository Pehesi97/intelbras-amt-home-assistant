# Changelog

## 1.0.0b5 — candidata major, não publicada

Inclui os fixes da 0.7.4 e reorganiza as informações de zona. Esta beta separa
as mudanças de apresentação/entidades da atualização de manutenção.

### Melhorias da beta 5

- Issue #8: senha opcional para consultas de status, separada da senha de comandos.
  Na AMT 4010, permite usar a senha do computador sem alterar a senha usada para
  arme/desarme. Entradas existentes continuam usando a senha atual por padrão.
- Recusas `0xE1`/`0xE2` nas consultas incluem o código e orientação para conferir
  a senha específica. `0xE2` continua significando comando inválido; não é prova
  isolada de senha incorreta.
- Frame real da AMT 4010 Smart firmware 3.9 publicado na issue coberto por teste:
  recusa `0x5A` com `0xE5`, resposta válida de `0x5B` e consultas posteriores
  diretamente por `0x5B`. Validação física com senha separada na 4010 pendente.
- Download do diagnóstico confirmado pelo usuário no navegador. No aplicativo
  utilizado, o botão não gerou arquivo; nenhuma alteração no backend foi necessária.
- 99 testes locais e verificações nativas de senhas separadas, preservação da
  configuração antiga e ausência de ambas as senhas no diagnóstico.

### Melhorias da beta 4

- Entidades ficam indisponíveis durante desconexão e até o primeiro status válido;
  respostas e desconexões de conexões antigas não alteram a conexão atual.
- Reconfiguração nativa de porta/senha preserva a entrada e seus IDs. Senha vazia
  mantém a anterior. Porta ocupada é tratada como falha com nova tentativa.
- Opções nativas para intervalo de atualização e seleção de zonas/PGMs. A seleção
  desabilita sem apagar registros e respeita desabilitações manuais.
- Diagnóstico para download com campos explícitos, sem credenciais, endereços ou
  frames brutos. Inclui horário e contadores de consultas válidas/falhas.
- 92 testes locais; fluxos, seleção e disponibilidade validados também com classes
  reais do HA. Veja [uso e validação](docs/beta-options.md).

### Breaking changes e migração

- **Nome do sensor principal:** `Zona NN - Aberta` passa a `Zona NN`. O estado
  de abertura continua separado do nome. `unique_id` é preservado, portanto o
  `entity_id` de uma entidade já registrada permanece. Nomes personalizados
  pelo usuário prevalecem. Em uma instalação nova, IDs gerados automaticamente
  podem diferir dos IDs antigos com sufixo `_aberta`. Templates que procuram
  entidades pelo nome visível devem ser revistos.
- **Remoção das auxiliares:** violação, bypass, bateria baixa, tamper e curto
  deixam de ser entidades separadas. A atualização remove seus registros,
  inclusive os desabilitados, pela API nativa do HA. Ajuste dashboards e
  automações para os atributos do sensor principal antes de atualizar.
  Esta mudança substitui a estratégia da beta 1 de manter auxiliares desabilitadas.
- **Atributos novos no principal:** `violada`, `bypass`, `bateria_baixa`,
  `tamper` e `curto_circuito`. `null` significa informação indisponível; `false`
  significa que o status não indica o alerta. Bateria não é porcentagem.
  Gatilhos genéricos de estado sem `from`/`to` podem reagir a mudanças dos novos
  atributos mesmo sem mudança de abertura. Para observar abertura use
  `to: "on"`; para bateria, observe `attribute: bateria_baixa` explicitamente.
- **Tamper/curto no status parcial:** o segundo byte passa a mapear zonas 11–18,
  conforme ISECMobile R15, em vez de 9–16. IDs não mudam, mas a associação do
  alerta à zona é corrigida. Remova eventuais compensações feitas em automações.

### Entidade agrupada de problema (beta 3)

- Adicionada `Zona NN - Problema` para cada zona, com os cinco atributos de diagnóstico.
- Estado ligado se bateria baixa, tamper ou curto estiver verdadeiro. Bypass e
  memória de violação não indicam defeito e não acionam esse estado.
- Sem nenhum diagnóstico reportado, o estado é desconhecido. Havendo dados,
  o estado resume somente os diagnósticos disponíveis; os demais continuam `null`.
- Abertura mantém ID, estado e atributos. Duas entidades por zona, sem recriar
  as antigas auxiliares individuais.

### Preservado

- Estado principal de abertura, IDs e configurações dos sensores principais.
- Comandos de arme/desarme, sirene, PGM, partições e entidades globais.
- Configurações de todas as entidades que permanecem; sem alteração de `disabled_by`.

Veja [a migração por atributos](docs/zone-attributes.md). Faça backup antes de
instalar. Para voltar com as personalizações das auxiliares, restaure o backup
completo (incluindo o registro de entidades) com o HA parado. Reinstalar apenas
a versão antiga pode não recuperar essas personalizações.

## 0.7.4 — publicada em 2026-09-14

Base: v0.7.3. Mantém nomes, IDs, atributos, classes e defaults de habilitação
das entidades, além do parser de zonas usado pela v0.7.3.

### Corrigido

- **#9:** reconhecimento explícito da AMT1000 Smart (`0x36`), mantendo consulta
  parcial e eliminando o warning de modelo desconhecido a cada consulta.
- **#10:** com partições habilitadas, o caminho `triggered + armado global`
  exige uma zona violada. Isso filtra a abertura sem violação descrita na issue;
  o painel permanece armado quando outra partição está armada. Os caminhos por
  sirene e o comportamento sem partições permanecem iguais. Logs distinguem o
  filtro de partições de uma central inteiramente desarmada.
- **#10:** links de documentação/reporte no manifest corrigidos para o
  repositório `Pehesi97/intelbras-amt-home-assistant`.
- **#11 / transporte:** ACK `FE` para identificação, heartbeat e eventos B0/B4;
  processamento de eventos durante consultas; callback de heartbeat sem bloquear
  a recepção; limpeza de consultas em timeout, cancelamento e desconexão; correção
  da resposta que chega durante o envio. Senha removida do log bruto de envio.

### Limites conhecidos das duas candidatas

- A mitigação #10 não associa zonas a partições nem distingue memória antiga
  de uma violação atual. Pânico silencioso sem zona ou sirene pode não ser
  reconhecido em centrais particionadas se reportar apenas o bit global.
- Status binário e comandos existentes são preservados. Não foi adicionada
  limpeza automática de memória nem exigência de sinal de fechamento de sensor.
- Testes físicos na AMT2018 E/EG 8.5 verificaram comandos, disparo silencioso,
  memória e continuidade de atualização do Cloud após disparo. Não foram
  recebidos B0/B4 nessa sessão. Os ACKs desses eventos foram testados em simulador;
  isso não prova a causa específica da interrupção do Cloud na #11.
- Não houve validação física em AMT1000, AMT4010 ou com partições habilitadas.

A v0.7.4 foi publicada como release estável. A validação da estrutura antiga
na 0.7.4 e da apresentação nova na major é feita separadamente.

## Validação das candidatas — 14/09/2026

- **0.7.4:** 56 testes passaram em uma cópia isolada da fonte. O código de
  entidades de zona e o parser de status foram comparados byte a byte com
  v0.7.3; os nomes, atributos e defaults anteriores foram mantidos.
- **1.0.0b1:** 77 testes passaram em outra cópia isolada. Instalada no HA
  Container 2026.8.1 após backup; imports/propriedades também verificados com
  as classes reais dessa versão do HA.
- Após reinício, HTTP 200 e central reconectada. Registro preservou os 263
  IDs e as 19 entidades desabilitadas, além dos nomes personalizados. O sensor
  existente da zona 25 manteve seu ID, passou a mostrar `Zona 25` e os cinco
  atributos. O painel permaneceu desarmado. Arquivos instalados conferidos por hash.
- Este teste de atualização não inclui um novo disparo, teste de partições ou
  bateria fisicamente baixa. Os limites de hardware descritos acima continuam.

### Atualização para 1.0.0b2

- 77 testes passaram também na fonte isolada da beta 2.
- Instalada no HA 2026.8.1 após backup do componente e do registro de entidades.
- Removidas exatamente 172 auxiliares de zona: a integração passou de 263 para
  91 entidades. IDs, nomes personalizados e desabilitações das 91 restantes
  preservados; nenhuma entidade nova foi criada.
- Registro persistido conferido após o atraso de gravação de inicialização do HA.
  Os 30 arquivos de runtime instalados conferem com a candidata por SHA-256.
- Zona 25 mantém os cinco atributos; central conectada, desarmada, sirene desligada.
- Adicionado exemplo de cartão nativo para visualizar atributos sem novas entidades.
- A candidata 0.7.4 permanece inalterada. Nenhuma release/tag foi publicada.

### Atualização para 1.0.0b3

- 88 testes passaram na fonte isolada, incluindo falhas independentes da abertura,
  memória/bypass sem defeito, ausência de diagnóstico e preservação na migração.
- Instalada no HA 2026.8.1 com backup do componente e registro. Acrescentadas 48
  entidades de problema; as 91 existentes preservaram IDs e configurações.
  Total desta instalação: 139 entidades.
- Zona 25 de problema confirmou estado desligado e cinco atributos; zona 41
  confirmou estado desconhecido por ausência dos três diagnósticos.
- Estados on/off/desconhecido também verificados com classes reais do HA e
  dados sintéticos, sem enviar comandos à central. Não houve teste de falha física.
- Central reconectada, desarmada, sirene desligada. Arquivos instalados conferidos
  por SHA-256. A candidata 0.7.4 permanece inalterada; nenhuma release publicada.

### Instalação da beta 4 no HA

- Validada no HA Container 2026.8.1, com backup anterior à instalação.
- O HA estava na 0.7.4 com 311 registros (incluindo entidades remanescentes da
  beta 3). A migração removeu exatamente 172 auxiliares, mantendo 139 entidades,
  seus IDs, nomes personalizados e desabilitações. As opções permaneceram vazias,
  conservando a seleção padrão de zonas/PGMs.
- Central reconectada e desarmada, interface HTTP 200 e 32 arquivos de runtime
  verificados por SHA-256. O comportamento de desconexão e os fluxos que mudam
  configuração foram testados em instância temporária do HA, sem alterar a
  senha, porta ou seleção efetiva da instalação do usuário.
- A v0.7.4 está publicada no GitHub. A beta 4 permanece separada, sem publicação.
