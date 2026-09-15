# Configuração da integração

Abra **Configurações → Dispositivos e serviços → Intelbras AMT → Reconfigurar**.
As alterações salvam as credenciais usadas pelo HA; não mudam as senhas gravadas
na central.

## Conexão e senha de usuário

A central inicia a conexão com o servidor da integração. Ao alterar a porta TCP
na integração, ajuste também o destino configurado na central.

Em todos os modelos suportados (AMT 2018 E/EG/E SMART, AMT 1000 Smart e
AMT 4010), a senha de usuário de 4–6 dígitos controla arme/desarme, sirene e PGMs. Escolha **Manter
configuração atual** ou **Definir ou substituir senha**; preencha o campo apenas
para substituir. A senha existente nunca aparece no formulário.

Quando essa senha também é usada nas consultas, a alteração é validada com uma
leitura antes de salvar. Quando há uma senha de consulta separada, o formulário
valida apenas o formato da senha de usuário: não envia arme/desarme para testá-la.

## Consulta de status

Nas AMT 2018 E/EG/E SMART e AMT 1000 Smart, normalmente deixe a senha de
consulta vazia para usar a senha de usuário. Na AMT 4010, se a consulta exigir
a senha do computador, informe essa credencial no campo de consulta. Nesta seção é possível manter ou
substituir essa senha, ou selecionar **Usar a senha de usuário nas consultas**
para remover a credencial específica.

A nova credencial efetiva é testada por leitura antes de salvar. Senha rejeitada,
falha de conexão ou mudança de conexão durante o teste preservam os dados anteriores.
A senha de consulta não autentica a limpeza de disparos.

## Limpar disparo (beta) — senha do computador

Configure a senha de acesso remoto de **6 dígitos**, usada no AMT Remoto Mobile por **IP Local**. Não é a senha de usuário.
Na AMT 4010, mesmo que a senha do computador já esteja no campo de consulta,
informe-a também nesta seção: cada campo tem uma função independente.
Escolha manter, definir/substituir ou **Desativar Limpar disparo**, que remove
somente essa credencial. A configuração testa autenticação e leitura, encerra a
sessão e só então salva; não limpa disparos durante o teste.

Recurso **beta** para **AMT 2018 E/EG/E SMART, AMT 1000 Smart e AMT 4010**; a compatibilidade
pode variar conforme o firmware. É necessário que o HA alcance o IP de origem da conexão da central na porta
TCP 9009. Conexões recebidas através de NAT/proxy podem não oferecer esse acesso.
Não há mudança no transporte dos controles existentes ou nas configurações de rede da central.

O botão **Limpar disparo (beta)** limpa a memória de todas as zonas, preservando a
programação e o histórico do HA. Exige status atual, todas as partições desarmadas
e sirene desligada. Abre uma sessão autenticada curta, verifica novamente a central,
envia a limpeza uma vez, confirma a memória e encerra a sessão. Sem confirmação,
apresenta erro; não simula um estado limpo nem repete automaticamente o comando.
Se a memória já estiver vazia, não envia outra limpeza.

Não é executado automaticamente no desarme, no início da integração ou na
reconfiguração. A sessão de programação pode ocupar temporariamente o teclado,
assim como o AMT Remoto Mobile; ela não permanece aberta entre operações.

A atualização preserva IDs, personalizações, seleção e credenciais existentes.
A senha do computador é opcional e não é inferida da antiga senha de consulta.
O botão requer configurar explicitamente essa nova credencial.

## Opções e diagnóstico

Em **Opções**, selecione zonas e PGMs e o intervalo de consulta (1–60 segundos).
Retirar uma entidade da seleção desabilita sem apagar IDs ou personalizações;
entidades desabilitadas manualmente continuam assim. Lista vazia desabilita a categoria.

**Baixar diagnóstico** inclui modelo, firmware e estatísticas de leitura, sem
senhas, endereços ou frames brutos. Os contadores reiniciam ao recarregar a integração.


## Logs

Consulte **Configurações → Sistema → Logs** e procure por `intelbras_amt`.
O nível INFO registra mudanças de arme/desarme e operações de limpeza confirmadas.
Para investigar comunicação, use **Ativar registro de depuração** na integração,
reproduza o problema e desative a depuração para baixar o arquivo.

Se houver uma configuração manual de logger em DEBUG, altere para INFO:

```yaml
logger:
  default: info
  logs:
    custom_components.intelbras_amt: info
```
