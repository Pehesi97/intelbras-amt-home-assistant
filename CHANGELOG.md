# Changelog

## 1.1.0 — 2026-09-14

- Sensor Data/Hora desativado por padrão para novas entidades.
- Sensor Último arme/desarme com número do usuário, quando informado pela central.

## 1.0.0 — 2026-09-14

### Adicionado

- Sensor de problema por zona, agrupando bateria baixa, tamper e curto-circuito.
- Reconfiguração de porta e senhas sem recriar a integração.
- Seleção de zonas e PGMs nas opções, preservando IDs e personalizações.
- Senha opcional para consulta de status, separada da senha de comandos. Na
  AMT 4010, a consulta pode exigir a senha do computador.
- Download de diagnóstico sem senhas, endereços de rede ou frames brutos.

### Corrigido

- Entidades ficam indisponíveis durante desconexão e voltam após receber status válido.
- Falha ao abrir a porta permite nova tentativa de configuração.
- Tamper e curto no segundo byte do status parcial passam a corresponder às
  zonas 11–18, em vez de 9–16.
- Inclui as correções de transporte e partições da versão 0.7.4.

### Migração da versão 0.x

- **As entidades auxiliares de violação, bypass, bateria baixa, tamper e curto
  são removidas**, inclusive quando desabilitadas. Esses dados passam aos
  atributos do sensor de zona. Ajuste dashboards e automações antes de atualizar.
- O nome padrão `Zona NN - Aberta` passa a `Zona NN`. IDs existentes e nomes
  personalizados são preservados.
- Para automações de abertura, use `to: "on"`: mudanças de atributos também
  podem acionar gatilhos genéricos de estado.
- Remova eventuais compensações manuais para o mapeamento de tamper/curto.

Faça backup antes de atualizar. Reinstalar a versão antiga não recupera as
personalizações das entidades removidas; para isso, restaure o backup completo.
Veja o [guia de migração](docs/zone-attributes.md).

## 0.7.4 — 2026-09-14

- Reconhecimento da AMT 1000 Smart, com consulta de status parcial (#9).
- Redução de falsos disparos com partições: o bit global de disparo junto ao
  arme exige uma zona violada (#10).
- Correção dos links de documentação e reporte de problemas.
- Confirmação de identificação, heartbeat e eventos B0/B4; recepção de eventos
  durante consultas e tratamento de timeout, cancelamento e desconexão (#11).
- Remoção da senha dos logs de envio.

Mantém a estrutura de entidades da versão 0.7.3.
Consulte os [limites conhecidos](docs/protocol-review.md).
