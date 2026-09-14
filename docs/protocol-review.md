# Revisão do SDK Intelbras e issues 9, 10 e 11

Revisão de 11/09/2026 sobre o código-base `c23eb89`. Fontes locais:
`/Users/pedro/Downloads/SDKCentraisdealarme`. A numeração abaixo se refere às
páginas físicas dos PDFs; alguns cabeçalhos do SDK têm totais de páginas incorretos.

## Documentos e alcance

- **ISECnet - Centrais Alarme / Intelbras Receptor IP, R14**, na pasta
  `Documentação AMT 8000 V02`: apesar do nome da pasta, o escopo da página 1 inclui
  expressamente AMT2018E/EG, AMT1016 NET e AMT4010 Smart. É a referência para o
  papel de receptor que esta integração assume.
- **ISECNet - Smartphones / Intelbras Receptor IP, R15**, na pasta
  `Protocolo_de_comunicacao_AMT`: comandos E9, respostas e status 5A/5B.
- **ISEC Net - AMT Remoto e AMT Mobile / Receptor IP, R05**, e exemplos TXT de
  conexão: descrevem também o cliente de um receptor existente, que é um papel
  diferente do servidor implementado aqui.
- **Comandos entre o software e a central AMT 2000 / AMT 3000, R05**, e
  **AMT4010 Smart, R14**: comandos internos, memória de disparos e menu de sirene.
- Exemplos TXT de checksum e CRC, usados para distinguir o XOR externo do CRC
  dos comandos internos. Os exemplos de transações E9 e B0/B4 servem como vetores
  de teste literais.

Os documentos de fotos e o mapa EEPROM específico da AMT8000 não são evidência de
endereços ou capacidades da AMT2018/4010/1000. Esta revisão não implementa suporte
à AMT8000, recepção de fotos ou programação da EEPROM.

## Diferenças fundamentais e decisão

| Tema | SDK | Código-base | Decisão nesta alteração |
| --- | --- | --- | --- |
| ACK de identificação/heartbeat | R14, §§6.1 e 6.8, pp. 3 e 16: um byte `FE`, sem tamanho/checksum | Enviava `01 FE 00` | Corrigido na construção do ACK curto |
| Eventos da central | R14, §§6.3 e 6.4, pp. 6-9: B0 tem 16 bytes de conteúdo, B4 tem 28, ambos exigem `FE` | Não confirmava nenhum deles; durante polling podia descartar o evento | ACK antes de despachar o evento; preservar a consulta pendente e entregar aos callbacks |
| Resposta a comandos E9 | R15, pp. 6-8: ACK/NACK da operação fica encapsulado em E9, por exemplo `02 E9 FE EA` | Encapsulamento correto | Preservado; ACK curto do receptor não substitui ACK E9 |
| Leitura durante heartbeat | A central pode responder a consultas e transmitir eventos pela mesma conexão | Leitor aguardava callback que podia aguardar uma resposta do próprio leitor | Uma tarefa de heartbeat por conexão, cancelada ao desconectar; rajadas não acumulam tarefas |
| Resposta durante envio | Recepção é independente de `drain()` | O leitor podia limpar `pending_response` antes de o envio começar a aguardá-lo | Referência local ao Future e limpeza em sucesso, timeout, cancelamento ou erro |
| Identificação AMT1000 | O código `0x36` e uso de 5A vêm do relato funcional da issue #9; não foram encontrados nesses PDFs | Usava fallback parcial e emitia warning a cada consulta | Enum, nome e seleção explícita de status parcial; preservar fallback dos desconhecidos |
| Bit de disparo | R15, pp. 10 e 14: lista `0x44` e `0x04` para disparo | Usa `func_byte & 0x04` | Ambos contêm bit 2; isso não justifica usar `0x40` sozinho nem inferir um novo disparo |
| Data/hora | R15, pp. 10 e 14: dígitos por nibble (BCD) | Interpreta bytes como inteiros binários | Preservado: capturas da #11 incluem ano `0x1A` e minuto `0x0A`, inválidos em BCD. Não aplicar conversão global sem evidência por modelo/firmware |
| Memória de disparos | Comandos internos R05 p. 8 e R14 p. 9: comando `0x1C` limpa a indicação de zonas que dispararam recentemente | Não implementa limpeza; trata flags como estado para o painel | Registrar hipótese e capturar eventos/restaurações antes de mudar a decisão de disparo. Não limpar memória automaticamente |
| Tamper/curto no status parcial | R15, p. 11: primeiro byte corresponde às zonas 1-8; segundo às zonas 11-18 | Trata os dois bytes como zonas 1-16 | Corrigido posteriormente na candidata de atributos de zona, no parser compartilhado e com teste dos extremos; ainda não instalado no HA do usuário |
| Sirene no status completo | R15, p. 16: Status46, bit 2, informa saída da sirene | Parser da 4010 ignora esse bit e usa só o byte geral; parser parcial também consulta Status38 | Divergência concreta; validar a fonte do estado da saída separadamente da decisão de alarme |
| Retorno de arme/desarme | R15, pp. 6-7, prevê ACK/NACK | Entidades enviam com `wait_response=False` | Mantido nesta entrega para não reintroduzir o problema que motivou `c23eb89`; ausência de espera não significa execução confirmada |
| Tempos de resposta | R14, p. 1: 30/60 s, central aguardando receptor; R15, p. 1: 8/15 s, consultas via Ethernet/GPRS | Timeout padrão de consulta de 8 s | São direções/papéis diferentes. Não aumentar indiscriminadamente o timeout para 30 s |

O checksum externo dos exemplos corresponde ao XOR de todos os bytes anteriores,
seguido de XOR com `FF`. Tamanho, senha ASCII, delimitadores `21`, comandos de
arme/desarme, consulta, PGM e sirene conferem com os exemplos de transações.
Há erros editoriais no SDK: exemplos rotulados como senha de seis dígitos contêm
`1234`; o exemplo tabular de desligar sirene usa tamanho `0A`, enquanto o exemplo
contínuo usa corretamente `08`. Os testes preservam o frame coerente com o
conteúdo e o checksum, sem copiar esses erros de legenda.

Os handshakes E0/E3/E4 dos TXT são de **aplicativo → receptor**, na porta 9010.
Não devem ser enviados automaticamente à central que conecta ao nosso receptor
na porta 9009. Tampouco o comando interno de limpeza `0x1C` pode ser tratado como
um comando E9 de um byte sem implementar o protocolo interno correspondente.

## Issue 11: o que foi corrigido e o que falta comprovar

Há três defeitos de transporte demonstráveis sem hardware: ACK com formato errado,
ausência de ACK de eventos e bloqueio da recepção pelo callback de heartbeat.
Uma central que continua vendo status consultado pelo HA pode, ao mesmo tempo,
estar aguardando confirmação de seus eventos. Portanto, receber status no HA
não prova que a sessão de monitoramento está correta.

As mudanças corrigem esses defeitos de acordo com o SDK. A relação causal com a
interrupção do Intelbras Cloud ainda precisa de validação na central afetada:
o SDK não especifica aqui a política de fila/retransmissão entre IP1 e IP2.
Na revisão inicial não houve acesso à central real. Em 14/09/2026 a candidata foi
instalada no HA do usuário, conforme registro parcial abaixo. As configurações
da central não foram alteradas.

Eventos conhecidos são confirmados após validação do frame/checksum e do tamanho
documentado. Eventos inválidos não recebem ACK; comandos desconhecidos não são
confirmados indiscriminadamente. B5/B6/B7 e identificação Cloud 95 não foram
adicionados como supostos equivalentes de B0/B4.

## Issue 10: bipes, partições e indicação persistente

Após os testes físicos de transporte, foi acrescentada localmente uma mitigação
para a #10, ainda não instalada no HA do usuário. Com partições habilitadas,
`triggered && armed` exige também uma zona violada. Sem partições, esse caminho
permanece igual. Os caminhos existentes por sirene também foram preservados.
O filtro independe do modelo e cobre os status de 43 e 54 bytes. Não verifica
se a zona violada pertence à partição armada: não há esse vínculo no status.

O caso relatado (A desarmada, B armada, zona aberta, bit global de disparo,
nenhuma zona violada e sirene desligada) foi reproduzido contra a entidade real
em testes locais: falhou nos dois formatos antes da mudança e passou depois.
Os logs agora distinguem esse filtro do caso inteiramente desarmado, incluindo
o estado das partições. A semântica do painel global continua agregada.

**Limitações aceitas para esta tentativa:** memória antiga de zona violada
ainda pode confirmar um bit global; pânico silencioso sem zona associada nem
sirene não é confirmado por esse caminho quando há partições, se a central
reportar apenas esses campos. Esse último formato não foi validado em hardware.
Não foi adicionado atraso nem exigência de zona aberta ou sinal de fechamento.

A observação do usuário amplia o caso: há um bipe ao armar e dois ao desarmar,
e o estado persistente pode aparecer no Cloud sem partições habilitadas.

A regra atual tem três caminhos problemáticos para esse cenário:

1. `triggered && armed` aceita o bit persistente ao rearmar, sem nova violação.
2. `triggered && siren_on` pode aceitar o bit persistente junto do bipe de desarme.
3. O fallback de sirene sustentada mede o intervalo entre amostras ligadas. Duas
   amostras não provam que a sirene permaneceu ligada entre elas: pode ter havido
   bipes distintos e estados desligados não observados pelo polling.

Exigir zona violada não resolve comprovadamente a persistência, pois existe
memorização de disparos no protocolo. A documentação não demonstra que os bits
de 5A/5B correspondam exatamente à memória limpa pelo comando interno 1C;
o teste físico confirmou a limpeza pelo teclado, sem executar esse comando.
Sirene sozinha também não diferencia alarme, acionamento manual e confirmação
sonora. Exigir sirene em todos os casos poderia esconder alarmes silenciosos.

O fato de o Cloud também indicar disparo não pode ser explicado apenas por uma
propriedade de entidade do HA: ela só interpreta dados. É necessário separar
indicação da central, eventual estado mantido pelo Cloud, fila de eventos sem ACK
e decisão de apresentação do HA. Não há evidência suficiente para escolher uma
dessas causas como única explicação.

O próximo diagnóstico deve correlacionar, numa mesma sequência temporal:
status bruto, partições, zonas abertas/violadas, saída da sirene, eventos Contact-ID
e restaurações. B0/B4 contêm qualificador, código e partição/zona; o SDK remete à
norma Contact-ID para a semântica completa. A correção de transporte passa a
preservar esses eventos no evento HA já existente `intelbras_amt_frame_received`.
Isso fornece evidência para distinguir episódio atual e indicação antiga sem
inventar um mapa zona→partição nem limpar informações da central.

## Verificação automática

Executar da raiz: `python -m pytest -q`.

- Vetores literais do SDK para 94, F7, B0 e B4: ACK exato `FE`.
- ACK E9 preservado; frame curto não consome o frame seguinte.
- Heartbeats em rajada, eventos e ACK tardio intercalados durante status 5A/5B.
- Checksum inválido, tamanho de evento inválido e comando desconhecido sem ACK.
- Resposta durante `drain`, erro de escrita, cancelamento, timeout e desconexão.
- Desconexão cancela tarefa de heartbeat; consultas liberam o lock e o Future.
- Detecção e polling de 2018, 2018 Smart, 1000 Smart, 4010 e modelo desconhecido;
  fallback para status completo quando a 4010 não responde a status parcial.
- Frames de arme/desarme, sirene e PGM preservados; montagem de evento fragmentado.
- Três capturas reais da #11 preservam flags, zonas, bytes e data binária.
- Capturas reais da AMT2018 antes/depois de Apagar e de um disparo silencioso.
- Decisão real do painel com status de 43/54 bytes: falso disparo particionado,
  disparo silencioso com zona violada, desaparecimento do bit de abertura,
  desarme com memória, comportamento sem partições, bipes e fallback de sirene.
- Atributos de zona, disponibilidade por formato, transições de bateria/violação,
  IDs legados, defaults de cadastro e mapeamento parcial de tamper/curto 11–18.
- Transações em sockets TCP reais de loopback: identificação, heartbeat, consulta
  5A/5B, B0/B4 intercalados e novos eventos após a primeira consulta.

Os testes de coordinator e painel substituem as dependências importadas do HA e
exercitam o código real de detecção/polling e da entidade de alarme. Não validam
o scheduler, o ciclo de vida completo das entidades ou a instalação HACS. Os testes de transporte
usam streams em memória e uma central simulada em TCP de loopback; não equivalem
a uma validação no Intelbras Cloud. Resultado local: **77 testes passaram** em
Python 3.14.7. O sandbox exige permissão para abrir os sockets de loopback.
O workflow adicionado executa a suíte em Python 3.11 e 3.14; execução remota no
GitHub Actions depende de publicar a alteração.

## Roteiro de validação na central afetada

Com a versão candidata instalada e em uma janela de teste controlada:

1. Registrar modelo/firmware, modo de comunicação com os dois servidores e
   intervalo de consulta. Habilitar temporariamente debug do logger
   `custom_components.intelbras_amt.lib.server.tcp_server` via `logger.set_level`.
   Não publicar senhas ou identificação da instalação nos logs compartilhados.
2. Confirmar conexão e heartbeat com ACK `FE`. Verificar que eventos B0/B4 geram
   ACK também enquanto há consulta pendente, sem timeout causado por heartbeat.
3. Fazer a sequência de disparo/restauração/desarme já usada para reproduzir a
   #11. Verificar entrega no HA **e no Cloud**, incluindo novos eventos depois
   do primeiro disparo. Registrar retransmissões, queda/reconexão e falha de
   comunicação. Não considerar o primeiro estado correto como teste completo.
4. Repetir arme/desarme com bipes e sem novo disparo, depois de uma ocorrência
   real. Comparar os dados da central com as indicações do HA e do Cloud.
5. Na 4010, repetir movimento em partição desarmada com outra armada e um disparo
   real controlado em partição armada. Verificar que a confirmação de eventos e
   a consulta de 54 bytes continuam funcionando.
6. Na AMT1000 Smart, verificar reconhecimento de `0x36`, consulta 5A e ausência
   do warning recorrente. Conferir que entidades e automações existentes foram
   preservadas.

**Critério para encerrar #11:** o problema original deixa de ocorrer na central
afetada, e novos eventos continuam chegando ao Cloud depois da sequência de
disparo/restauração. Ainda pendente de execução física.

**Critério para uma futura correção de #10:** eliminar os falsos nas duas
configurações (com/sem partições) sem ocultar disparo real ou silencioso, sem
tomar bipes como disparo e sem apagar automaticamente memória/configuração.

## Validação física parcial - 14/09/2026

- Home Assistant Container 2026.8.1, Python 3.14.6; AMT2018 E/EG, firmware 8.5.
- A instalação anterior correspondia ao código-base revisado. Backup realizado;
  cinco arquivos de runtime substituídos após conferência de hashes. Logger do
  transporte habilitado temporariamente para coleta.
- Importação da candidata no Python do HA e validação do YAML passaram. Container
  reiniciado; interface HTTP retornou 200, e a central reconectou com ACK `FE`.
- Primeira amostra após reinício: 18 respostas de status, sem timeout. Ainda não
  havia evento B0/B4 ou heartbeat nessa janela; portanto seus ACKs na central
  real e a continuidade de entrega ao Cloud ainda não estavam validados.
- Com a central desarmada, sem partições e com sirene desligada, o status bruto
  retornou `func_byte=0x44`, `triggered=True`, zonas abertas vazias e zonas
  violadas 25 e 26. A indicação persistente também está presente sem partições;
  exigir zona violada como única confirmação adicional não elimina esse caso.
- Nenhum comando de arme, desarme ou acionamento de sirene foi emitido pelo
  agente. Teste físico guiado e conferência do aplicativo Cloud pendentes.
- Em seguida, o usuário confirmou que o Cloud mostrava múltiplas zonas em
  disparo com a central desarmada. Pressionou **Apagar** no teclado, conforme
  seção 5.4 do manual do usuário, e o Cloud passou a mostrar apenas desarmada.
  O status bruto também mudou: `func_byte` de `0x44` para `0x00`,
  `triggered=False` e zonas violadas vazias, mantendo desarme e sirene desligada.
  Capturas anteriores e posteriores foram preservadas em teste de parsing.
  Isso demonstra que, neste firmware/cenário, o bit pode representar uma
  indicação memorizada; não prova que uma falha de ACK tenha causado o estado.
  Testes de arme/desarme com bipes e entrega após novo disparo ainda pendentes.
- Primeiro arme após a limpeza: usuário confirmou HA e Cloud indicando apenas
  armado. Comando registrado às 17:07:50; status às 17:08:10 com
  `func_byte=0x08`, `armed=True`, `triggered=False`, sirene desligada e zonas
  violadas vazias. Nenhum B0/B4 apareceu nessa coleta; a confirmação de estado
  via consulta não valida ainda a recepção/ACK de eventos Contact-ID.
- Desarme às 17:09:02: usuário confirmou ausência de indicação de disparo no HA
  e no Cloud, inclusive durante os bipes. Status às 17:09:24 com
  `func_byte=0x00`, desarmada, `triggered=False`, sirene desligada e zonas
  violadas vazias. A sequência sem memória prévia passou; o cenário após um
  disparo real continua pendente.
- Teste com sensor da zona 25: arme às 17:10:10, desarme via HA às 17:10:17.
  Usuário relatou a zona 25 ainda indicada como disparada no Cloud após desarme.
  Às 17:10:18 o status confirmou desarmada, sirene desligada, zonas abertas
  vazias, zona 25 violada e `func_byte=0x44`. A coleta não capturou uma amostra
  com sirene ligada/alarme ativo entre o arme e desarme; portanto não confirma
  a detecção do disparo ativo pelo HA. Até 17:11:06 foram recebidos 362 frames
  E9 e uma identificação 94, nenhum B0/B4. Não há evidência de ACK de eventos
  nessa conexão real; o status continua chegando após a ocorrência. Próximo
  teste: novo arme/desarme sem Apagar, observando estado e atualização no Cloud.
- Rearme sem Apagar às 17:11:55: usuário informou acompanhamento nos aplicativos
  e ausência de indicação de disparo no Cloud. Às 17:11:56, a própria central
  limpou a zona 25 memorizada e retornou `func_byte=0x08`, armada e
  `triggered=False`. A amostra capturou sirene ligada no Status38 (`0x44`),
  seguida de desligada às 17:11:58 (`0x40`), compatível com o bipe relatado.
  Até 17:12:30 a última amostra ainda indicava armada; o desarme desta sequência
  ainda não foi confirmado nos registros. A coleta total seguia sem B0/B4.
- Desarme confirmado às 17:13:18: `func_byte=0x00`, `triggered=False`, zonas
  violadas vazias. Capturado bipe com Status38 `0x44`, seguido de `0x40` às
  17:13:20, sem bit de disparo. Às 17:13:30 a central continuava desarmada e
  com sirene desligada. Foram recebidos 438 frames E9 e uma identificação 94;
  nenhum B0/B4. Resta capturar o alarme ativo por tempo suficiente para observar
  o estado no HA, pois o primeiro teste passou de arme a desarme em sete segundos.
- Teste silencioso realizado pelo usuário na zona 25: arme às 17:19:51;
  às 17:20:06 a central retornou `func_byte=0x4C`, armada, `triggered=True`,
  sirene desligada e zona 25 aberta/violada. O painel HA registrou explicitamente
  `TRIGGERED` por `triggered_armed`. O bit de zona aberta zerou às 17:20:08,
  mantendo a indicação de disparo. Isso não confirma fechamento físico nem
  recepção de um sinal de fechamento. Desarme às 17:20:58; às 17:21:00 status desarmado,
  sirene desligada, `func_byte=0x44`, zona 25 apenas na memória de violadas.
  O HA ignorou esse bit para o painel desarmado. Usuário confirmou indicação
  residual no Cloud e sensor de zona violada como "Problema" no HA; esse sensor
  usa `BinarySensorDeviceClass.PROBLEM` e lê diretamente `violated_zones`.
  As três capturas foram acrescentadas aos testes. Exigir sirene ou zona aberta
  para reconhecer todo disparo ocultaria estados reais observados neste teste.
  Até 17:22:34: 714 frames E9 e uma identificação 94, ainda sem B0/B4.
  Restaurar o modo original da zona 25 após o teste silencioso e encerrar a
  coleta temporária continuam pendentes.
- Esclarecimento do usuário: sensores sem fio configurados para transmitir
  somente na abertura, sem transmissão no fechamento. Logo, não é válido
  condicionar restauração/desarme ao recebimento de fechamento, nem interpretar
  o bit aberto zerado como confirmação física de porta fechada. Teste e relato
  acima corrigidos para descrever apenas a transição observada do bit.
  O usuário também informou que o teclado não indicava disparo, embora o Cloud
  indicasse; Apagar limpou Cloud e HA. Às 17:26:50 o status bruto confirmou
  desarmada, `func_byte=0x00`, sirene desligada e zonas violadas vazias. Portanto,
  ausência de indicação visível no teclado não provou ausência de memória
  reportada pela central. Não há evidência de que transmitir fechamento no
  sensor limparia essa memória; isso depende do conjunto sensor/central/receptor.
- Encerrada a coleta detalhada: removido somente o logger temporário; o YAML
  voltou exatamente ao conteúdo do backup. HA reiniciado às 17:28:13, HTTP 200,
  central reconectada às 17:28:24 e modelo detectado às 17:28:34. Candidata
  mantida instalada; 46 testes locais passaram e `git diff --check` limpo.
  Não houve leitura/verificação da programação da zona 25: restauração do modo
  original depende da confirmação do usuário. Validação física de ACK B0/B4
  e dos modelos AMT1000/4010 permanece pendente.
- Usuário confirmou a restauração da configuração sonora original da zona 25.
  Encerrada esta rodada de testes físicos, sem alterações temporárias de zona
  ou logging pendentes conhecidas. As limitações de validação acima permanecem.

## Candidatas separadas e atualização para a major

Foram preparadas 0.7.4 (56 testes, estrutura antiga de entidades e parser de
zonas iguais à v0.7.3) e 1.0.0b1 (77 testes, atributos agrupados e nome `Zona NN`).
O manifest antigo estava em 0.1.0 apesar da tag v0.7.3; as candidatas alinham
manifest e pyproject aos seus números. Nenhuma tag/release foi publicada.

Com autorização do usuário, a major foi instalada em 14/09/2026 após backup em
`/config/intelbras_amt_backups/major-1.0.0b1-20260914T224755Z`. Foram substituídos
quatro arquivos em relação à candidata de transporte instalada anteriormente.
Imports e propriedades das entidades passaram no Python do HA com classes reais.
Container reiniciado às 22:48:32 UTC; HTTP 200 e reconexão da central confirmados.
Comparação do registro preservou 263 `entity_id`, seus `unique_id`, nomes
personalizados e as 19 desabilitações. O estado da zona 25 mostrou o nome novo e
atributos, mantendo o ID com sufixo `_aberta`. Painel desarmado e conectado;
hashes dos 30 arquivos de runtime iguais aos da fonte major testada.
Não foram acionados alarme, sirene ou sensores pelo agente nessa atualização.


## Major 1.0.0b2 — remoção das auxiliares (14/09/2026)

A pedido do usuário, a beta 2 substitui a preservação das auxiliares da beta 1
por remoção seletiva via API nativa do registro. Backup anterior à atualização:
`/config/intelbras_amt_backups/major-1.0.0b2-20260914T225906Z`.
Somente `binary_sensor.py` e `manifest.json` precisaram ser substituídos no HA.

77 testes passaram na fonte isolada. Após reinício e persistência do registro,
foram confirmadas 172 exclusões e 91 entidades mantidas, todas com os mesmos IDs,
nomes personalizados e desabilitações. A central reconectou desarmada, com sirene
desligada. O estado registrado da zona 25 contém `violada`, `bypass` e
`bateria_baixa` falsos; `tamper` e `curto_circuito` nulos. Nenhum disparo foi
provocado nesta atualização. Hashes de todos os arquivos instalados conferidos.

O registro do HA adia gravações por 180 segundos durante inicialização; a primeira
leitura em disco ainda continha as auxiliares, e a leitura após esse prazo
confirmou a remoção. Os atributos são visíveis nos Estados das ferramentas do
desenvolvedor ou em linhas `type: attribute` de um cartão Entities.


## Major 1.0.0b3 — entidade de problema por zona (14/09/2026)

Backup: `/config/intelbras_amt_backups/major-1.0.0b3-20260914T230907Z`.
Foram alterados somente `binary_sensor.py` e `manifest.json` no HA instalado.
88 testes passaram na fonte isolada. Um teste com as classes reais do HA e
status sintético confirmou falha e abertura independentes, restauração e estado
desconhecido quando nenhum diagnóstico é reportado.

O registro salvo confirma 48 entidades novas de problema, todas habilitadas,
e as 91 anteriores com IDs e configurações preservados (139 no total).
O HA adicionou o prefixo de área `quarto_visitas` aos novos entity IDs; o cartão
de exemplo usa o ID realmente criado. Zona 25 de problema está desligada,
com bateria baixa falsa e tamper/curto nulos; zona 41 está desconhecida porque
nenhum dos três diagnósticos é reportado. Os cinco atributos estão nas duas
entidades de cada zona. A central reconectou desarmada e com sirene desligada.
Não houve disparo provocado nem teste físico de bateria, tamper ou curto.
