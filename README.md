# Windows US-International for Linux

Digitação parecida com o teclado **US-International do Windows**, usando Fcitx5 e XKB no Linux.

Corrige `ć`, `ḿ` e `ś` inesperados. Mantém os acentos, evita a prévia destacada de `´` e deixa a primeira seta funcionar depois de um acento pendente. Não cria outro daemon.

| Digite em sequência | Resultado |
| --- | --- |
| `'` e `e` | é |
| `'` e `c` | ç |
| `'` e `m` | `'m` |
| `'` e `s` | `'s` |
| `~` e `a` | ã |
| `"` e `u` | ü |
| Backtick e `e` | è |
| `'` e Espaço | `'` |

Os cinco acentos continuam sendo teclas mortas. Pressionar só o acento espera a próxima tecla; não insere pontuação imediatamente.

## Requisitos

- Linux com XKB e **Fcitx5 5.1.23 ou superior**, já funcionando na sessão.
- Compilador C++20, Make, pkg-config e Python 3.10 ou superior.
- libxkbcommon, xkeyboard-config, `xkbcli` e os cabeçalhos de desenvolvimento do Fcitx5.
- Para a configuração automática do Hyprland: Omarchy com `~/.config/hypr/input.lua` em Lua.

No Arch Linux, as dependências de compilação estão nestes pacotes:

```sh
sudo pacman -S --needed base-devel pkgconf python fcitx5 libxkbcommon xkeyboard-config
```

Em outras distribuições, os cabeçalhos podem estar em pacotes separados, como `-dev` ou `-devel`.

## Instalar

Na pasta do repositório:

```sh
make
make check
python3 tools/install.py install --hyprland --dry-run
python3 tools/install.py install --hyprland
```

Execute o instalador **sem sudo**. O modo `--dry-run` apenas lista as mudanças.

No Omarchy, ative os arquivos instalados:

```sh
omarchy restart xcompose
hyprctl reload
hyprctl configerrors
```

Se um mapa anterior com o mesmo nome continuar em cache, encerrar e iniciar a sessão recarrega tudo. O instalador não encerra programas nem reinicia serviços automaticamente.

### Outros compositores

Instale sem `--hyprland`:

```sh
python3 tools/install.py install
```

Depois selecione o layout XKB `us_windows_intl` no compositor e reinicie o Fcitx5 pela forma usada na sua sessão. A instalação não configura o método de entrada dos aplicativos.

## Usar

Use o teclado normalmente. A tecla Compose e seus atalhos existentes, incluindo os emojis do Omarchy, continuam disponíveis.

- Setas, Home, End, Tab, Enter e Escape cancelam um acento pendente e seguem para o aplicativo.
- Backspace cancela o acento pendente sem apagar o caractere anterior.
- Trocar de campo ou usar um atalho com Ctrl, Alt ou Super cancela o acento pendente.
- AltGr segue os níveis publicados pela Microsoft para US-International.

Para conferir, digite em um campo novo:

```text
é ç ã õ ê ü
i'm it's don't i'll we'd we're
```

O navegador precisa usar uma integração funcional com o Fcitx5. Alterar apenas o layout XKB não ativa essa integração. Não é necessário forçar Chromium para XWayland nas versões compatíveis com text-input-v3.

## O que a instalação muda

Todos os arquivos ficam no usuário. O instalador:

- Instala a extensão do Fcitx5 e o layout XKB.
- Acrescenta um bloco ao arquivo Compose em uso, normalmente `~/.XCompose`, preservando o conteúdo anterior.
- Preserva as regras XKB existentes e acrescenta o tipo necessário ao layout.
- Com `--hyprland`, acrescenta o override ao `input.lua`, sem substituir o arquivo.
- Guarda os originais em `~/.local/state/fcitx5-windows-us-intl`.

Os diretórios `XDG_CONFIG_HOME`, `XDG_DATA_HOME` e `XDG_STATE_HOME`, além de `XCOMPOSEFILE`, são respeitados. O instalador também reconhece um arquivo `$XDG_CONFIG_HOME/XCompose`. Ele recusa arquivos próprios já existentes e links simbólicos, em vez de sobrescrevê-los.

## Remover

Na mesma pasta do repositório:

```sh
python3 tools/install.py uninstall
omarchy restart xcompose
hyprctl reload
hyprctl configerrors
```

Fora do Omarchy, reinicie o Fcitx5 e recarregue o compositor da forma habitual.

A remoção restaura os originais e apaga os arquivos adicionados, os diretórios que ficaram vazios e o backup. Se algum arquivo tiver sido editado depois da instalação, ela para antes de restaurar qualquer arquivo. Preserve seus ajustes e consulte o backup para fazer a mesclagem; não apague o backup para contornar a verificação.

Para atualizar esta versão, remova a instalação anterior, execute `make clean`, compile novamente e instale. Uma instalação manual anterior precisa ser removida pelo seu próprio rollback antes de usar este instalador.

Uma atualização incompatível do Fcitx5 pode exigir recompilar o addon.

## Limites conhecidos

- As regras Compose e a extensão se aplicam aos métodos `keyboard-*` do usuário, não apenas ao layout selecionado. O português brasileiro comum foi exercitado na implementação original, mas algumas combinações especiais passam a seguir as regras Windows.
- Sequências com acentos diferentes continuam dependendo da tabela Compose existente.
- A política de cancelamento com setas foi testada no Linux, não comparada lado a lado com um Windows.
- Aplicativos que ignoram Fcitx5 ou recebem teclas diretamente podem ter outro comportamento.
- Não há promessa de paridade completa com o Windows nem de compatibilidade com todas as distribuições.

Veja [comportamento e testes](docs/testing.md) para os detalhes. Licença [MIT](LICENSE).
