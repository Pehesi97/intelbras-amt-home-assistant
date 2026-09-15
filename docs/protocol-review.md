# Compatibilidade e limites conhecidos

## Modelos

| Modelo | Consulta de status | Validação |
| --- | --- | --- |
| AMT 2018 E/EG | Parcial (`0x5A`) | Testada em hardware |
| AMT 2018 E SMART | Parcial (`0x5A`) | Validação física pendente |
| AMT 1000 Smart | Parcial (`0x5A`) | Compatibilidade relatada; testes automatizados |
| AMT 4010 | Completa (`0x5B`) | Frame real coberto por teste; validação física da integração pendente |

A integração recebe a conexão da central e atua como receptor TCP. A comunicação
foi verificada com Home Assistant 2026.8.1. Outros firmwares e versões do HA
podem apresentar diferenças.

## Estado do alarme

- Com partições habilitadas, o bit global de disparo junto ao arme exige também
  uma zona violada. O status não informa o vínculo entre zona e partição.
- A memória de violação pode persistir após desarme. A integração não limpa essa
  memória automaticamente e não consegue distingui-la sempre de um novo disparo.
- Pânico silencioso sem zona associada ou sirene pode não ser reconhecido em
  centrais particionadas quando somente o bit global é reportado.
- Bipes de confirmação podem aparecer como sirene ligada. O tempo entre duas
  amostras ligadas não comprova que a sirene permaneceu ligada entre elas.
- Para sensores que transmitem somente abertura, o bit zerado não confirma
  fechamento físico. Veja os [atributos de zona](zone-attributes.md).

## Eventos e identificação do usuário

O sensor Último arme/desarme depende do envio de eventos Contact-ID B0/B4 ao
receptor. Consultas periódicas de status não identificam o usuário.

São reconhecidos os códigos 401 (usuário), 456 (arme parcial), 403 (automático),
407 (remoto) e 408 (uma tecla). Somente 401/456 fornecem identificação de usuário
nesta integração; os demais deixam o número vazio. Códigos personalizados não
são reconhecidos. A recepção desses eventos ainda precisa de validação física.

B4 inclui o horário local do evento; B0 registra apenas o recebimento no HA.
Eventos datados anteriores ao último evento também datado são ignorados, assim
como retransmissões idênticas desse evento. Sem data, uma retransmissão B0 não
pode ser distinguida de uma nova ação idêntica. O sensor atualiza junto à próxima
consulta de status válida e é limpo ao reiniciar ou recarregar a integração.

## Comunicação

- Identificação, heartbeat e eventos B0/B4 recebem ACK `FE`. Eventos são
  confirmados após validação do frame e do tamanho, mesmo durante consultas.
- O recebimento de status não comprova entrega de eventos ao Intelbras Cloud.
  A coexistência dos receptores depende da programação da central.
- O envio de arme/desarme não equivale à confirmação de execução; confira o
  estado reportado pela central.
- Na AMT 4010, a consulta pode exigir a senha do computador. Configure-a em
  [Reconfigurar](beta-options.md), preservando a senha apropriada aos comandos.
- Não há suporte a AMT 8000, fotos ou programação da EEPROM.

## Referências técnicas

A implementação usa os documentos Intelbras **ISECnet — Centrais Alarme / Receptor
IP, R14** e **ISECNet — Smartphones / Receptor IP, R15**. O calendário do status
é interpretado como binário conforme capturas reais; não se aplica conversão BCD
global. O mapeamento parcial de tamper/curto segue zonas 1–8 e 11–18. A indicação
de sirene no status completo da 4010 ainda requer validação específica.

Os testes em `custom_components/intelbras_amt/lib/tests` cobrem parsing,
transporte TCP simulado e regras de estado. O roteiro `ha_native_check.py`
verifica entidades e configuração com classes reais do Home Assistant.
Testes simulados não substituem a validação em cada modelo de central.
