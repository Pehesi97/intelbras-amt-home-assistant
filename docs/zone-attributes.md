# 1.0.0: detalhes da zona em atributos

Cada zona possui duas entidades: `Zona NN` para abertura e `Zona NN - Problema`
para falhas. As duas expõem os cinco atributos descritos abaixo. O sensor de
abertura existente mantém seu ID e os atributos introduzidos nas betas anteriores.
Seu estado continua representando apenas o bit de abertura recebido da central;
memória de disparo e bateria baixa não transformam esse estado em aberto.

Exemplo de atributos de uma zona 25 no status parcial (valores ilustrativos):

```yaml
zone_number: 25
zone_type: aberta
violada: true
bypass: false
bateria_baixa: false
tamper: null
curto_circuito: null
```

- `violada`: indicação de disparo/violação, que pode permanecer memorizada.
- `bypass`: indicação de zona anulada.
- `bateria_baixa`: alerta binário, sem porcentagem de carga.
- `tamper` e `curto_circuito`: alertas de sabotagem e curto da zona.
- `null`: dado ausente ou não representado para essa zona no status recebido.
- `false`: o status não indica o alerta; não comprova sensor cadastrado ou bateria saudável.

Como o usuário relatou sensores que transmitem somente abertura, o bit de abertura
zerado não comprova fechamento físico. Esses atributos não acrescentam informações
que a central não transmitiu.

## Entidade de problema

`Zona NN - Problema` usa a classe nativa `problem` do HA: ligado indica problema,
desligado indica ausência de alerta nos diagnósticos reportados. Ele liga quando
`bateria_baixa`, `tamper` ou `curto_circuito` é `true`. Abertura, `violada` e `bypass`
não acionam esse estado; os dois últimos continuam disponíveis como atributos.
O atributo `zone_type` desta entidade é `problema`.

Se os três diagnósticos forem `null`, o estado será desconhecido. Havendo ao menos
um diagnóstico reportado, ele avalia os disponíveis; os não reportados continuam
`null`. Um estado sem problema não certifica a saúde dos diagnósticos ausentes.
No status parcial, por exemplo, as zonas 41–48 não reportam nenhum desses três
diagnósticos, portanto suas entidades de problema permanecem desconhecidas.

Abertura e problema podem estar ligados simultaneamente. Automações de falha podem
observar `to: "on"` na entidade de problema; use os atributos para identificar a causa.

## Onde visualizar

Abra **Ferramentas do desenvolvedor → Estados** e procure a entidade principal.
Nesta instalação: `binary_sensor.intelbras_amt_2018_4010_zona_25_aberta`.
Os cinco campos ficam nos atributos do estado. A tela de entidades/dispositivo
não cria linhas para cada atributo. No dashboard, use o cartão nativo
[Entities com linhas de atributo](https://www.home-assistant.io/dashboards/entities/#attribute).
Veja [um cartão pronto para a zona 25](zone-25-card.yaml); ajuste o ID em outras instalações.

## Breaking change: remoção das auxiliares

A major remove automaticamente do registro as entidades de zona de violação,
bypass, bateria baixa, tamper e curto. Elas deixam de ser criadas. A remoção usa
a API nativa do HA, limitada aos IDs conhecidos desta entrada da integração.
Na AMT2018, ficam 48 entidades de abertura e 48 de problema; na AMT4010,
64 de cada. Os nove problemas
globais, sensores de resumo e controles permanecem.

O sensor principal mantém o `unique_id`, o `entity_id` já registrado e suas
configurações. O nome padrão passa a `Zona NN`; nomes personalizados prevalecem.
Instalações novas podem gerar IDs sem o sufixo `_aberta`.

Antes de atualizar, adapte dashboards e automações que usam as auxiliares para
os atributos correspondentes no principal. Esses IDs auxiliares deixarão de existir,
inclusive se estiverem desabilitados. Não é necessário recadastrar a integração.

Faça backup de `/config` antes da atualização (incluindo a integração e o registro
de entidades). Para reverter preservando também as configurações das auxiliares
removidas, restaure o backup com o HA parado. Reinstalar apenas o código antigo
recria as auxiliares, mas não garante a recuperação de suas personalizações.

Um gatilho pode observar explicitamente `attribute: bateria_baixa` com `to: true`,
usando o ID real do sensor de zona aberta. Atributos podem mudar sem alteração
do estado aberto/fechado; gatilhos genéricos de estado sem `from`/`to` também
podem reagir a essas atualizações. Para observar apenas abertura, use `to: "on"`.

## Correção de mapeamento incluída

O SDK ISECMobile R15 especifica zonas 11–18 no segundo byte de tamper/curto do
status parcial. O parser usava 9–16. O mapeamento foi corrigido no parser
compartilhado, com teste dos dois extremos; os atributos
agora usam a leitura corrigida. Isso corrige a zona associada ao alerta
sem alterar IDs. Integrações que compensavam manualmente esse deslocamento
precisam remover a compensação. O status completo permanece com zonas 1–8.

## Conteúdo e validação

A versão 1.0.0 inclui também o reconhecimento AMT1000, as correções de transporte
e a mitigação de partições da #10. Os limites desta última, incluindo memória
antiga e pânico silencioso sem zona, estão em [protocol-review.md](protocol-review.md).

Os testes verificam os atributos, os limites dos formatos de status, a preservação
do ID principal e a remoção seletiva e idempotente das auxiliares. Os testes
unitários usam substitutos das dependências do HA; a atualização é verificada
separadamente no HA real, conforme [o changelog](../CHANGELOG.md).

A versão de manutenção **0.7.4** contém apenas os fixes das issues 9/10/11,
preservando a estrutura anterior de entidades. As mudanças descritas neste
documento pertencem exclusivamente à **1.0.0**. Consulte [o changelog](../CHANGELOG.md).
