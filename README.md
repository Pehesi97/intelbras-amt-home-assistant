# Intelbras AMT - Home Assistant Integration

Integração para Home Assistant que permite controlar centrais de alarme Intelbras via protocolo ISECNet/ISECMobile.

## Modelos Suportados

- ✅ **AMT 2018 E/EG** - Detecção automática (comando 0x5A)
- ✅ **AMT 4010** - Detecção automática (comando 0x5B)

A integração **detecta automaticamente** o modelo da central e usa o comando apropriado!

## Características

- ✅ **Controle completo do alarme** - Armar/desarmar via interface do Home Assistant
- ✅ **Monitoramento de zonas** - Acompanhe status de todas as zonas (abertas, violadas, bypass)
- ✅ **Controle de saídas** - Controle PGMs e sirene diretamente do Home Assistant
- ✅ **Sensores e binary sensors** - Informações detalhadas sobre o status da central
- ✅ **Configuração via UI** - Setup fácil através do Config Flow
- ✅ **Atualização automática** - Status atualizado periodicamente
- ✅ **Suporte a partições** - Controle individual de partições A, B, C e D
- ✅ **Detecção automática de modelo** - Suporta múltiplos modelos sem configuração
- ✅ **Servidor standalone** - Biblioteca reutilizável para outros projetos

## Requisitos

- **Home Assistant**: 2023.1.0 ou superior
- **Central Intelbras**: AMT 2018 E/EG ou AMT 4010 com firmware compatível
- **Conexão de rede** entre a central e o Home Assistant
- **Senha da central** (4-6 dígitos configurada na central)

## Como Funciona

A central Intelbras AMT **conecta ativamente** ao servidor TCP do Home Assistant e **mantém a conexão aberta**. O servidor:

1. Escuta na porta 9009 (configurável)
2. Aceita conexão da central
3. Responde automaticamente aos heartbeats (keep-alive)
4. Envia comandos quando você arma/desarma pelo HA

```
┌─────────────────────────────────────────────────┐
│              HOME ASSISTANT                     │
│  ┌───────────────────────────────────────────┐  │
│  │     Custom Component (intelbras_amt)      │  │
│  │                                           │  │
│  │  TCP Server ◄──── Central conecta aqui    │  │
│  │      :9009       (e mantém conexão aberta)│  │
│  │         │                                 │  │
│  │         ▼                                 │  │
│  │  alarm_control_panel                      │  │
│  │  - Armar (away/home)                      │  │
│  │  - Desarmar                               │  │
│  │  - Status                                 │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
             ▲
             │ TCP (conexão persistente)
             │ Heartbeats a cada 60 segundos
             │
      ┌──────┴──────┐
      │ Central AMT │
      │ 2018 / 4010 │
      └─────────────┘
```

## Status do Projeto

🟢 **Funcional** - Integração completa e testada com central real

| Componente | Status | Descrição |
|------------|--------|-----------|
| Protocolo ISECNet/ISECMobile | ✅ | Implementação completa do protocolo |
| Checksum XOR | ✅ | Cálculo de checksum ISECNet |
| CRC-16 | ✅ | Cálculo de CRC para ISECProgram |
| ISECNet Frame | ✅ | Builder/Parser da camada de transporte |
| ISECMobile Frame | ✅ | Builder/Parser da camada de comandos |
| Comando 0x41 | ✅ | Ativar/Armar central (todas partições ou específica) |
| Comando 0x44 | ✅ | Desativar/Desarmar central (todas partições ou específica) |
| Comando 0x43 | ✅ | Ligar sirene |
| Comando 0x63 | ✅ | Desligar sirene |
| Comando 0x50 | ✅ | Controle de PGM (ligar/desligar saídas 1-19) |
| Comando 0x5A | ✅ | Solicitação de status parcial (43 bytes) |
| Comando 0x5B | ✅ | Solicitação de status completo (54 bytes) |
| Comando 0x94 | ✅ | Identificação da central (conta, canal, MAC) |
| Comando 0xF7 | ✅ | Heartbeat (keep-alive) |
| Respostas ACK/NACK | ✅ | Parser de todas as respostas |
| Servidor TCP | ✅ | Servidor asyncio porta 9009 |
| Home Assistant Integration | ✅ | Integração completa com múltiplas entidades |
| Config Flow | ✅ | Configuração via UI do Home Assistant |
| Testes | ✅ | Testes unitários abrangentes |

### Entidades Disponíveis

A integração expõe as seguintes entidades no Home Assistant:

#### Alarm Control Panel
- **Alarme** - Controle principal do alarme (armar/desarmar, modo away/home)

#### Switches
- **Armar Alarme** - Switch para armar/desarmar todas as áreas
- **Sirene** - Switch para ligar/desligar a sirene
- **PGM 1-19** - Switches para controlar cada saída programável
- **Partição A/B/C/D** - Switches para armar/desarmar partições individuais

#### Sensors
- **Modelo** - Modelo da central (hex)
- **Firmware** - Versão do firmware
- **Data/Hora** - Data e hora da central
- **Zonas Abertas** - Contagem e lista de zonas abertas
- **Zonas Violadas** - Lista de zonas violadas (ex: "26" ou "26, 30")
- **Zonas em Bypass** - Contagem e lista de zonas em bypass
- **Sirene** - Status da sirene (Ligada/Desligada)
- **Armada** - Status de armamento geral

#### Binary Sensors
- **Zonas (1-48)** - Binary sensors para cada zona:
  - Zona aberta
  - Zona violada
  - Zona em bypass
- **Zonas (1-18)** - Binary sensors adicionais:
  - Tamper
  - Curto-circuito
- **Zonas (1-40)** - Bateria baixa (sensores sem fio)
- **Problemas do Sistema**:
  - Falta de Energia
  - Bateria Baixa
  - Bateria Ausente
  - Bateria em Curto
  - Sobrecarga Auxiliar
  - Fio Sirene Cortado
  - Curto Sirene
  - Linha Telefônica Cortada
  - Falha Comunicação

## Instalação no Home Assistant

### Opção 1: Via HACS (Recomendado)

1. Certifique-se de que o [HACS](https://hacs.xyz/) está instalado no seu Home Assistant

2. No HACS, vá em **Integrações** → **Menu (⋮)** → **Repositórios Customizados**

3. Adicione este repositório:
   - **URL**: `https://github.com/pehesi97/intelbras-amt-homeassistant`
   - **Categoria**: Integração

4. Procure por "Intelbras AMT 2018/4010" no HACS e clique em **Baixar**

5. Reinicie o Home Assistant

6. Vá em **Configurações → Dispositivos e Serviços → Adicionar Integração**

7. Busque por "Intelbras AMT 2018/4010"

8. Configure:
   - **Porta TCP**: 9009 (ou outra porta disponível)
   - **Senha**: A senha de 4-6 dígitos configurada na central

### Opção 2: Instalação Manual (Custom Components)

1. Acesse a pasta `custom_components` do seu Home Assistant:
   - **Home Assistant OS/Supervised**: `/config/custom_components/`
   - **Home Assistant Container**: No volume mapeado para `/config/custom_components/`
   - **Home Assistant Core**: No diretório de configuração do HA

2. Copie a pasta `custom_components/intelbras_amt` para dentro de `custom_components/`:
   ```bash
   # Exemplo no Home Assistant OS
   cp -r custom_components/intelbras_amt /config/custom_components/
   ```

3. Certifique-se de que a estrutura está correta:
```
├── custom_components/
│   └── intelbras_amt/          # ← Custom Component para Home Assistant
│       ├── __init__.py         # Setup: inicia servidor TCP
│       ├── alarm_control_panel.py  # Entidade do alarme
│       ├── binary_sensor.py    # Binary sensors (zonas, problemas)
│       ├── sensor.py           # Sensors (status, contadores)
│       ├── switch.py           # Switches (PGMs, sirene, partições)
│       ├── coordinator.py      # Data update coordinator
│       ├── config_flow.py      # Configuração via UI
│       ├── const.py
│       ├── manifest.json
│       ├── translations/
│       │   └── pt-BR.json     # Traduções em português
│       └── lib/               # ← Biblioteca de protocolo
│           ├── __main__.py    # Servidor standalone
│           ├── const.py
│           ├── protocol/
│           │   ├── checksum.py         # Checksum XOR e CRC-16
│           │   ├── isecnet.py          # Frame ISECNet (transporte)
│           │   ├── isecmobile.py       # Frame ISECMobile (comandos)
│           │   ├── responses.py        # Parser ACK/NACK
│           │   └── commands/
│           │       ├── activation.py   # Comando 0x41 (armar)
│           │       ├── deactivation.py # Comando 0x44 (desarmar)
│           │       ├── siren.py        # Comandos 0x43/0x63
│           │       ├── pgm.py          # Comando 0x50 (controle PGM)
│           │       ├── status.py       # Comandos 0x5A/0x5B
│           │       └── connection.py   # Comando 0x94
│           ├── server/
│           │   ├── tcp_server.py      # Servidor TCP asyncio
│           │   └── connection_manager.py
│           └── tests/                 # Testes unitários
└── run_server.py               # ← Wrapper para rodar servidor standalone
```

4. Reinicie o Home Assistant

5. Vá em **Configurações → Dispositivos e Serviços → Adicionar Integração**

6. Busque por "Intelbras AMT 2018/4010"

7. Configure:
   - **Porta TCP**: 9009 (ou outra porta disponível)
   - **Senha**: A senha de 4-6 dígitos configurada na central

### Configuração da Central AMT 2018 / 4010

Após instalar a integração, configure a central para conectar ao Home Assistant:

1. Acesse o modo de programação da central AMT 2018 / 4010

2. Configure o **IP do servidor** (IP do seu Home Assistant)

3. Configure a **porta: 9009** (ou a porta que você configurou na integração)

4. A central iniciará a conexão TCP automaticamente e aparecerá como conectada no Home Assistant

> **Nota:** A central é o *client* e o Home Assistant é o *server*. A central inicia a conexão e envia heartbeats periodicamente para manter a conexão ativa.

## Instalação (Desenvolvimento)

### Com uv (recomendado)

```bash
# Instalar uv (se ainda não tiver)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Faça um fork deste repositório e clone o repositório criado
git clone https://github.com/<seu usuário>/intelbras-amt-homeassistant.git
cd intelbras-amt-homeassistant

# Instalar dependências e criar venv automaticamente
uv sync

# Executar testes
uv run pytest -v

# Executar servidor standalone
uv run python run_server.py
```

### Com pip (alternativo)

```bash
# Faça um fork deste repositório e clone o repositório criado
git clone https://github.com/<seu usuário>/intelbras-amt-homeassistant.git
cd intelbras-amt-homeassistant

# Crie um ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instale as dependências
pip install -e ".[dev]"

# Execute os testes
pytest -v
```

## Uso da Biblioteca

### Construir comandos

```python
from custom_components.intelbras_amt.lib.protocol.commands import (
    ActivationCommand,
    DeactivationCommand,
    PGMCommand,
    SirenCommand,
    StatusRequestCommand,
    PartialStatusRequestCommand,
    CentralStatus,
    PartialCentralStatus,
)

# Armar todas as partições
cmd = ActivationCommand.arm_all(password="1234")
packet = cmd.build()
print(packet.hex(' '))  # 08 e9 21 31 32 33 34 41 21 5b

# Armar partição específica
cmd_a = ActivationCommand.arm_partition_a(password="1234")
cmd_b = ActivationCommand.arm_partition_b(password="1234")
cmd_stay = ActivationCommand.arm_stay(password="1234")

# Desarmar todas as partições
cmd_disarm = DeactivationCommand.disarm_all(password="1234")

# Desarmar partição específica
cmd_disarm_a = DeactivationCommand.disarm_partition_a(password="1234")

# Controlar PGM
cmd_pgm_on = PGMCommand.turn_on(password="1234", pgm_number=1)   # Liga PGM 1
cmd_pgm_off = PGMCommand.turn_off(password="1234", pgm_number=2)  # Desliga PGM 2

# Controlar Sirene
from intelbras_amt.protocol.commands import SirenCommand
cmd_siren_on = SirenCommand.turn_on_siren(password="1234")   # Liga sirene
cmd_siren_off = SirenCommand.turn_off_siren(password="1234")  # Desliga sirene

# Solicitar status completo
cmd_status = StatusRequestCommand(password="1234")
# Após receber resposta de 54 bytes:
# status = CentralStatus.parse(response_data)
# print(status.armed, status.zones.open_zones, status.partitions.partition_a_armed)

# Solicitar status parcial (mais rápido, 43 bytes)
cmd_status_partial = PartialStatusRequestCommand(password="1234")
# Após receber resposta de 43 bytes:
# status = PartialCentralStatus.parse(response_data)
# print(status.armed, status.zones.violated_zones, status.siren_on)
```

### Iniciar servidor e enviar comandos

```python
import asyncio
from custom_components.intelbras_amt.lib.server import AMTServer
from custom_components.intelbras_amt.lib.protocol.commands import ActivationCommand

async def main():
    server = AMTServer()
    
    @server.on_connect
    async def on_connect(conn):
        print(f"Central conectada: {conn.id}")
        
        # Enviar comando de ativação
        cmd = ActivationCommand.arm_all(password="1234")
        response = await server.send_command(
            conn.id,
            cmd.build_net_frame(),
            wait_response=True
        )
        
        if response.is_success:
            print("✓ Alarme armado com sucesso!")
        else:
            print(f"✗ Erro: {response.message}")
    
    @server.on_disconnect
    async def on_disconnect(conn):
        print(f"Central desconectada: {conn.id}")
    
    # Heartbeats (0xF7) são respondidos automaticamente
    print("Aguardando conexão da central na porta 9009...")
    await server.serve_forever()

asyncio.run(main())
```

### Parsear respostas

```python
from custom_components.intelbras_amt.lib.protocol.responses import Response
from custom_components.intelbras_amt.lib.protocol.isecnet import ISECNetFrame

# Parsear frame recebido
frame = ISECNetFrame.parse(raw_bytes)
response = Response.from_isecnet_frame(frame)

if response.is_success:
    print("Comando executado!")
else:
    print(f"Erro: {response.message}")
    # Possíveis erros:
    # - Senha incorreta
    # - Zonas abertas
    # - Comando inválido
    # - etc.
```

## Protocolo ISECNet/ISECMobile

Não temos uma explicação completa do protocolo aqui pois a Intelbras requer assinatura de documentos para a liberação da SDK.

## Rodar Servidor (Desenvolvimento)

Para testar a comunicação com sua central sem o Home Assistant:

```bash
# Inicia servidor na porta 9009
uv run python run_server.py

# Com porta e senha customizados
uv run python run_server.py --port 9009 --password 1234

# Modo verbose (mostra heartbeats)
uv run python run_server.py -v

# Ou com python direto (sem uv)
python3 run_server.py --port 9009 --password 3007 --verbose
```

O servidor interativo aceita os seguintes comandos:

#### Comandos de Armamento
- `arm` - Armar todas as partições
- `arm a|b|c|d` - Armar partição específica (A, B, C ou D)
- `arm stay` - Armar no modo Stay
- `disarm` - Desarmar todas as partições
- `disarm a|b|c|d` - Desarmar partição específica

#### Controle de Saídas
- `pgm <1-19> on|off` - Controlar saída PGM (ex: `pgm 1 on`, `pgm 2 off`)
- `siren on` - Ligar a sirene
- `siren off` - Desligar a sirene

#### Consulta de Status
- `info` - Solicitar status completo da central (comando 0x5B, 54 bytes)
- `info-partial` - Solicitar status parcial da central (comando 0x5A, 43 bytes)
- `status` - Ver conexões TCP ativas e estatísticas

#### Outros
- `help` - Mostrar ajuda com todos os comandos
- `quit` ou `exit` - Encerrar servidor

## Executar Testes

```bash
# Todos os testes
uv run pytest -v

# Apenas testes de checksum
uv run pytest -v custom_components/intelbras_amt/lib/tests/test_checksum.py

# Apenas testes de protocolo
uv run pytest -v custom_components/intelbras_amt/lib/tests/test_isecnet.py
```

## Troubleshooting

### A central não conecta ao Home Assistant

1. **Verifique o IP e porta**: Certifique-se de que a central está configurada com o IP correto do Home Assistant e a porta 9009 (ou a porta que você configurou)

2. **Firewall**: Verifique se o firewall do Home Assistant permite conexões TCP na porta configurada

3. **Rede**: Confirme que a central e o Home Assistant estão na mesma rede ou que há roteamento adequado

4. **Logs**: Verifique os logs do Home Assistant para erros:
   ```bash
   # No Home Assistant, vá em Configurações → Sistema → Logs
   # Procure por "intelbras_amt" ou "AMT"
   ```

### Comandos não funcionam

1. **Senha incorreta**: Verifique se a senha configurada na integração corresponde à senha da central (4-6 dígitos)

2. **Central desconectada**: Verifique se a central está conectada (status na integração)

3. **Timeout**: Se houver timeouts, verifique a conexão de rede e se a central está respondendo

### Entidades não aparecem

1. **Reinicie o Home Assistant** após instalar a integração

2. **Verifique os logs** para erros de carregamento

3. **Limpe o cache** do navegador se as entidades não aparecerem na interface

### Status não atualiza

1. O coordinator atualiza o status periodicamente (padrão: a cada 30 segundos)

2. Você pode forçar uma atualização manualmente através do serviço `homeassistant.update_entity`

3. Verifique se a central está enviando heartbeats (verifique os logs)

**Estrutura unificada:** Todo o código está em `custom_components/intelbras_amt/`!
- **`lib/`** - Biblioteca de protocolo (servidor, protocolo)
- **Raiz** - Integração Home Assistant (coordinator, entidades)

## Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/novo-comando`)
3. Faça suas modificações em `custom_components/intelbras_amt/`
4. Execute os testes (`uv run pytest -v`)
5. Commit suas mudanças (`git commit -m 'Adiciona comando X'`)
6. Push para a branch (`git push origin feature/novo-comando`)
7. Abra um Pull Request

## Licença

MIT

## Referências

- Documentação ISECNet/ISECMobile da Intelbras
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [HACS](https://hacs.xyz/)

