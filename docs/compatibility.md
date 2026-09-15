# Compatibilidade e limites conhecidos

| Modelo | Consulta de status | Limpar disparo |
| --- | --- | --- |
| AMT 2018 E/EG | Parcial | Beta |
| AMT 2018 E SMART | Parcial | Beta |
| AMT 1000 Smart | Parcial | Beta |
| AMT 4010 | Completa | Beta |

O modelo é detectado automaticamente. A compatibilidade dos comandos de
programação depende também do firmware; o recurso beta pode ser recusado
mesmo em um modelo contemplado.

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
são reconhecidos.

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
  [Reconfigurar](configuration.md), preservando a senha apropriada aos comandos.
- Não há suporte a AMT 8000, fotos ou programação da EEPROM.

## Limpeza de disparos (beta)

Exige senha do computador e conexão local do HA à central na porta TCP 9009.
Remove a memória de todas as zonas, sem apagar a programação da central ou o
histórico do HA. Todas as partições devem estar desarmadas e a sirene desligada.
Sem autenticação, formato de status reconhecido ou confirmação de limpeza, a
operação apresenta erro. Não há repetição automática nem limpeza no desarme.

A sessão é encerrada ao terminar a operação e pode ocupar temporariamente o
teclado, como uma conexão do AMT Remoto Mobile. A configuração valida acesso
sem limpar a memória. Veja o [guia de configuração](configuration.md).
