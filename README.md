# Intelbras AMT para Home Assistant

Integração local para controlar e acompanhar centrais Intelbras AMT pelo Home Assistant.

## Modelos suportados

| Modelo | Monitoramento e controles | Limpar disparo |
| --- | --- | --- |
| AMT 2018 E/EG | Sim | Beta |
| AMT 2018 E SMART | Sim | Beta |
| AMT 1000 Smart | Sim | Beta |
| AMT 4010 | Sim | Beta |

O modelo é detectado automaticamente. Recursos disponíveis dependem da central
e do firmware. Consulte os [limites de compatibilidade](docs/compatibility.md).

## Instalação

### HACS

1. Em **HACS → Repositórios personalizados**, adicione
   `https://github.com/Pehesi97/intelbras-amt-home-assistant` na categoria **Integração**.
2. Baixe **Intelbras AMT 2018/4010** e reinicie o Home Assistant.
3. Abra **Configurações → Dispositivos e serviços → Adicionar integração** e
   procure por **Intelbras AMT 2018/4010**.
4. Informe a porta TCP e a senha de usuário da central. A senha de consulta é opcional;
   veja a tabela abaixo antes de preenchê-la.

### Instalação manual

Copie `custom_components/intelbras_amt` deste repositório ou do ZIP da release
para `/config/custom_components/intelbras_amt`, reinicie o Home Assistant e
adicione a integração pela interface.

### Conexão da central

A **central inicia a conexão** com o Home Assistant. Configure na central o
IP do Home Assistant como servidor de destino e a mesma porta TCP informada
na integração (padrão: **9009**). Essa porta deve estar acessível pela central.

O Home Assistant recebe eventos e consulta o estado pela conexão persistente.
Não é necessário informar o IP da central no formulário. Ao mudar a porta em
**Reconfigurar**, ajuste também o destino na central.

## Qual senha usar

| Campo | Função | Aplicação |
| --- | --- | --- |
| Senha de usuário, 4–6 dígitos | Armar/desarmar, controlar sirene e PGMs; consultar status quando não há senha separada | Todos os modelos suportados |
| Senha para consulta de status, opcional | Apenas leitura de status | Nas AMT 2018 e 1000 Smart, normalmente deixe vazio. Na AMT 4010, informe a senha do computador se ela for exigida para consulta |
| Senha do computador, 6 dígitos | Autenticar a limpeza de disparos | AMT 2018 E/EG/E SMART, AMT 1000 Smart e AMT 4010; mesma senha usada no AMT Remoto Mobile por IP Local |

A senha do computador para limpeza é configurada em **Reconfigurar → Limpar
disparo (beta)**. Na AMT 4010, mesmo que essa senha seja usada na consulta,
informe-a também na seção de limpeza para habilitar o botão.

Reconfigurar altera as credenciais usadas pela integração; não muda as senhas
gravadas na central. As senhas salvas nunca são exibidas nos formulários.
Consulte o [guia de configuração](docs/configuration.md).

## Entidades

- **Alarme** e **Armar Alarme**: arme/desarme geral; controles de partições quando disponíveis.
- **Sirene** e **PGMs**: controle das saídas da central.
- **Zona NN**: abertura, com atributos `violada`, `bypass`, `bateria_baixa`,
  `tamper` e `curto_circuito`.
- **Zona NN - Problema**: indica bateria baixa, tamper ou curto; possui os mesmos
  atributos da zona. Memória de disparo e bypass não acionam esse estado.
- **Problemas do sistema**: energia, bateria, sirene, linha telefônica e comunicação,
  conforme os dados fornecidos pela central.
- **Sensores de resumo**: modelo, firmware, zonas abertas, violadas e em bypass,
  sirene, armamento e data/hora. Data/hora é desativado por padrão em novas instalações.
- **Último arme/desarme**: ação, número de usuário, partição e horário quando
  informados pelos eventos da central. Reiniciar ou recarregar limpa essa informação.
- **Limpar disparo (beta)**: limpeza manual da memória de todas as zonas.

**Zonas Violadas mostra números de zona**, não uma contagem: `26` significa zona 26.
A memória pode permanecer após desarmar. Sensores sem fio que transmitem somente
abertura não permitem comprovar o fechamento físico pela ausência de indicação.
Atributos não disponíveis aparecem como `null`, em vez de `false`.
Veja [como usar os atributos das zonas](docs/zone-attributes.md).

### Limpar disparo (beta)

O botão exige senha do computador configurada, central conectada, todas as
partições desarmadas e sirene desligada. O HA precisa alcançar o IP local da
central na **porta TCP 9009**, além da conexão de monitoramento já existente.

A operação autentica, verifica o estado, limpa a memória e exige confirmação
por nova leitura. Não apaga a programação ou o histórico do HA, não repete o
comando automaticamente e não executa limpeza ao desarmar ou reiniciar.
A sessão pode ocupar temporariamente o teclado e é encerrada após a operação.

O recurso permanece **beta**: a compatibilidade pode variar conforme modelo e
firmware. Sem confirmação da central, o botão apresenta erro.

## Opções, diagnóstico e logs

Em **Opções**, escolha zonas, PGMs e intervalo de atualização (1–60 segundos,
padrão: 2). Desmarcar uma zona desabilita suas entidades sem apagar IDs ou
personalizações; não desativa a zona na central nem elimina sua indicação dos resumos.

**Baixar diagnóstico** reúne modelo, firmware e estatísticas de comunicação,
sem senhas, endereços ou frames brutos. Os logs ficam em **Configurações →
Sistema → Logs**. INFO registra mudanças de arme/desarme; use a depuração
apenas durante uma investigação. Veja [configuração e logs](docs/configuration.md).

## Atualização

A **1.2.0 preserva as entidades, credenciais e opções da versão 1.x**.
A limpeza precisa ser habilitada explicitamente com a senha do computador.
Consulte o [changelog](CHANGELOG.md).

Ao migrar da **0.x para a 1.x**, as antigas entidades auxiliares de violação,
bypass, bateria baixa, tamper e curto de cada zona são removidas. Os dados
passam aos atributos de `Zona NN`; `Zona NN - Problema` agrupa os alertas.
Faça backup e adapte automações e dashboards seguindo o
[guia de migração](docs/zone-attributes.md). Não é necessário recadastrar a integração.

## Desenvolvimento

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

O código da integração fica em `custom_components/intelbras_amt`; `lib` contém
protocolo, transporte e servidor standalone. Para executar o servidor interativo:

```bash
python run_server.py --port 9009
```

Use `--help` para opções e `help` no terminal interativo para listar os comandos.

## Licença

[MIT](LICENSE).
