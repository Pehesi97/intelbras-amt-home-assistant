# Configuração da integração

Abra **Configurações → Dispositivos e serviços → Intelbras AMT**.

## Reconfigurar

Altere a porta TCP e as senhas sem recriar a integração. Campos de senha vazios
mantêm o valor atual. Ao trocar a porta, ajuste também o destino na central.

- **Senha para comandos:** usada para arme, desarme e demais controles.
- **Senha para consulta de status:** opcional. Na AMT 4010, pode ser necessário
  informar a senha do computador. Sem ela, as consultas usam a senha de comandos.
  Para substituir uma senha específica pela mesma dos comandos, informe esse valor
  nos dois campos.

## Opções

- **Intervalo de atualização:** de 1 a 60 segundos, com padrão de 2 segundos.
  Instalações existentes mantêm o valor salvo.
- **Zonas e PGMs:** selecione as entidades que deseja usar. Retirar da seleção
  desabilita sem apagar IDs ou personalizações; selecionar novamente as recupera.
  Entidades desabilitadas manualmente continuam assim. Uma lista vazia desabilita
  toda a categoria. Cada zona inclui os sensores de abertura e de problema.

Salvar a configuração recarrega a integração. As entidades ficam indisponíveis
até a central reconectar e enviar um status válido. A programação da central
não é alterada. Automações que dependem de entidades desabilitadas deixam de
receber suas atualizações.

## Diagnóstico

Use **Baixar diagnóstico** ao reportar um problema. O arquivo contém modelo,
firmware, disponibilidade e estatísticas de consultas, sem senhas, endereços de
rede ou frames brutos. Os contadores reiniciam ao recarregar a integração.
