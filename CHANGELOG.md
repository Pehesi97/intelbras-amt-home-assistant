# Changelog

## 0.7.4 — 2026-09-14

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

### Limites conhecidos

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

Esta versão preserva a estrutura de entidades da v0.7.3.


### Validação 0.7.4

56 testes passaram na fonte isolada. Entidades de zona e parser de status
comparados byte a byte com v0.7.3. A instalação física da sessão correspondeu
à candidata major; a 0.7.4 foi validada separadamente em testes locais.
