# Comportamento e testes

## Camadas

O XKB define as teclas e os níveis de Shift, AltGr e Caps Lock. O arquivo em `data/xkb/symbols` herda `us(intl)` e substitui os níveis que diferem do layout da Microsoft.

`data/xkb/types` corrige Caps Lock para `ß`, `µ` e `ç/Ç`. As regras do usuário carregam esses tipos apenas para `us_windows_intl`; os mapas físicos `us` e `br` continuam iguais.

A tabela em `data/compose` fornece as combinações Windows e o retorno literal para combinações sem acento. Ela é gerada por `tools/generate_compose.py`, sem consultar a configuração pessoal de quem compila.

O addon possui um estado de composição separado por campo. Ele não reutiliza nem reseta o estado nativo do Fcitx5. `Multi_key` continua sendo tratado pelo mecanismo nativo. A extensão não envia pré-edição para os cinco acentos tratados.

Os arquivos Compose são globais para o usuário. Não existe detecção automática do layout ativo neste projeto. Não use o projeto esperando que o comportamento de outros layouts fique completamente nativo.

## Testes automáticos

```sh
make check
```

O núcleo também pode ser verificado com AddressSanitizer, UndefinedBehaviorSanitizer e LeakSanitizer:

```sh
make check-sanitizers
```

LeakSanitizer precisa de acesso à inspeção do próprio processo. Ambientes sob `ptrace` ou sandboxes restritos podem impedir a execução; isso não equivale a um vazamento detectado.

A suíte cobre:

- Acentos, retorno literal, maiúsculas e caracteres fora da tabela explícita.
- Cancelamento, Backspace e isolamento entre contextos.
- Preservação de um Compose nativo já em andamento.
- Carregamento do addon real num Fcitx5 isolado, sem os módulos de Wayland, X11 ou D-Bus.
- Ausência de pré-edição, atalhos e mudanças de foco nesse Fcitx5 isolado.
- Mapas XKB, AltGr, Caps Lock, layout individual e as quatro primeiras posições de uma lista de layouts.
- Ausência de mudanças nos mapas físicos US e ABNT2.
- Instalação e remoção em diretórios temporários, incluindo falha de escrita, links simbólicos, backup alterado e edições posteriores.

O teste do Fcitx usa diretórios XDG temporários e não substitui o processo da sessão. Os testes não instalam nada no usuário real.

O workflow do GitHub Actions prepara a mesma suíte num contêiner Arch Linux, como usuário sem privilégios. A execução no GitHub só pode ser confirmada depois de enviar o repositório.

Para regenerar a tabela:

```sh
python3 tools/generate_compose.py
make check
```

## Histórico dos testes interativos

A implementação anterior ao refactor foi exercitada com eventos sintéticos pelo protocolo de teclado virtual do Wayland em:

| Componente | Versão |
| --- | --- |
| Omarchy | 4.5.0-3 |
| Hyprland | 0.56.2-4 |
| Fcitx5 | 5.1.23-1 |
| Chromium | 155.0.8059.84-1, Wayland nativo |
| Foot | 1.28.0-2 |

Foram lidos os valores e eventos dos campos do Chromium, os bytes recebidos pelo terminal e imagens da barra de endereço. Também foram exercitados os mapas brasileiros com um teclado virtual ABNT2 completo, sem trocar o layout principal.

Esse histórico não equivale a um teste gráfico de cada build futuro. O código refatorado possui testes automatizados de integração com o Fcitx5, mas precisa de uma nova passagem gráfica antes de uma versão estável.

## Conferência manual após instalar

Teste em input, textarea, contenteditable, barra de endereço e terminal:

| Sequência | Resultado |
| --- | --- |
| `'` e `a/e/c/m/s` | `á/é/ç/'m/'s` |
| `~` e `a/o` | `ã/õ` |
| `"` e `u` | `ü` |
| Backtick e `e` | `è` |
| `'` e Espaço | `'` |
| `"` e Espaço | `"` |
| Acento sozinho | Nenhum texto ou destaque visível |
| Acento e seta | Nenhuma pontuação inserida; a primeira seta funciona |
| Compose do Omarchy, `m`, `s` | 😄 |

Confira maiúsculas, AltGr, Caps Lock e atalhos do aplicativo. Repita após encerrar e iniciar a sessão. GTK, Qt, Electron, XWayland e aplicativos que não usam Fcitx5 precisam de testes próprios; não foram certificados por esta suíte.

## Referências

- [Microsoft: United States-International, KLID 00020409](https://learn.microsoft.com/en-us/globalization/keyboards/kbdusx.html)
- [libxkbcommon: Compose e cancelamento](https://xkbcommon.org/doc/current/group__compose.html)
- [Fcitx5 5.1.23: composição do teclado](https://github.com/fcitx/fcitx5/blob/5.1.23/src/im/keyboard/compose.cpp)
- [Fcitx5 no Wayland](https://fcitx-im.org/wiki/Using_Fcitx_5_on_Wayland)
