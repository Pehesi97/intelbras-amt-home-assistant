# Beta 1.0.0b5: conexão, opções e diagnóstico

Na página da integração Intelbras AMT em **Configurações → Dispositivos e serviços**:

- **Reconfigurar**: altera porta TCP e senhas sem recriar a entrada. Senha vazia
  mantém a atual; ela não é preenchida no formulário. Ao trocar a porta, altere
  também o destino configurado na central. Portas usadas por outra entrada são
  rejeitadas; falha ao abrir a porta deixa a integração aguardando nova tentativa.
  **Senha para comandos** controla arme/desarme e os demais comandos. A nova
  **Senha para consulta de status** é opcional: sem ela, as consultas usam a senha
  de comandos. Se já estiver configurada, deixá-la vazia mantém seu valor anterior.
  Para usar o mesmo valor nas duas funções, preencha ambas com essa senha.
- **Opções**: altera intervalo de consulta (1–60 segundos) e seleciona zonas/PGMs.
  Uma zona seleciona seu sensor de abertura e seu sensor de problema juntos.
  Lista vazia desabilita todas as entidades daquela categoria. Na atualização,
  o padrão mantém todas as zonas do modelo e as 19 PGMs atuais.
- **Baixar diagnóstico**: exporta modelo, firmware, disponibilidade, intervalo,
  horário da última consulta válida, contadores de consultas e tipo do último
  erro de consulta. Não contém senha, IP, ID da entrada, nomes de zonas ou frames
  brutos. Contadores são reiniciados quando a integração é recarregada.
  Se o aplicativo não gerar arquivo, abra o HA no navegador e use o mesmo botão;
  o download pelo navegador foi confirmado nesta instalação.

Retirar uma entidade da seleção desabilita seu registro pela integração e remove
seu estado ativo após recarga. Selecioná-la novamente preserva o ID e recupera suas
personalizações. Uma entidade desabilitada manualmente pelo usuário permanece
assim até que ele a habilite. Automações dependentes de entidades retiradas da
seleção deixam de receber seus estados. Problemas globais, painel, sirene e
controles de partições permanecem disponíveis; a seleção atua em zonas e PGMs.

Sem conexão, as entidades ficam **indisponíveis**. Dados anteriores não são
apresentados como uma leitura atual de fechado/sem problema/desarmado. Após
reconexão, uma resposta válida torna as entidades disponíveis novamente. Respostas
e notificações de desconexão de conexões antigas são ignoradas.

A mudança de porta/senha e o salvamento de opções recarregam a integração. A
central precisa reconectar; o HA inteiro não precisa ser reiniciado para essas
alterações. As opções não mudam a programação de zonas/PGMs na central.

## Validação

99 testes locais e verificações com as classes reais do HA 2026.8.1: desconexão,
reconexão, respostas antigas, porta ocupada, senha mantida, porta duplicada,
limites de seleção, seleção vazia, desabilitação manual preservada e diagnóstico
sem dados sensíveis. O roteiro nativo usa configuração temporária e dados
sintéticos, sem comandar a central:

```sh
PYTHONMALLOC=malloc python -m custom_components.intelbras_amt.lib.tests.ha_native_check
```

Nesse container (Python 3.14.6), o processo temporário apresentou falha de GC ao
encerrar com o alocador padrão, após passar as verificações. Com o alocador do
sistema, passou e encerrou com código zero. A configuração do processo principal
do HA não foi alterada. Os limites físicos de modelos/partições continuam no
[relatório de protocolo](protocol-review.md).

## AMT 4010 Smart — issue #8

No [teste publicado pelo autor](https://github.com/Pehesi97/intelbras-amt-home-assistant/issues/8#issuecomment-5328597331),
a AMT 4010 Smart firmware 3.9 aceitou `0x5B` com a **senha do computador**, enquanto
a senha de acesso remoto recebeu `0xE2`. Configure a senha do computador no novo
campo de consulta, preservando no campo de comandos a senha apropriada para
arme/desarme. Não é necessário alterar instalações que já consultam normalmente.

A detecção tenta `0x5A` e, em caso de falha, `0x5B`; após detectar a 4010, usa
`0x5B` nas consultas seguintes. Os códigos `0xE1` e `0xE2` agora orientam a verificar
a credencial de consulta sem substituir seu significado original. O relato da
issue usou conexão cliente para a central; esta integração continua recebendo a
conexão da central. A senha separada e o frame publicado foram testados em software,
mas sua operação nesse sentido de conexão ainda precisa de validação física na 4010.
