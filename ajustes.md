# Ajustes Realizados nos Dotfiles do ASURA

Este documento registra todas as alterações, correções e padronizações realizadas na pasta `dotfiles`. A pasta `Asura-shell` não foi analisada nem modificada, conforme solicitado.

---

## 1. Desvinculação e Limpeza de Menções a Outros Dotfiles

- **BTOP (`dotfiles/btop/btop.conf`)**:
  - Alterado o parâmetro `color_theme` de `"noctalia"` para `"Asura"`, garantindo que o btop aponte para o tema gerado dinamicamente pelo Matugen (`btop/themes/Asura.theme`).

- **Kitty (`dotfiles/kitty/kitty.conf`)**:
  - Removida a linha residual legada `include themes/noctalia.conf`.
  - Mantidas as inclusões `include themes/Asura.conf` e `include current-theme.conf`.

- **Starship (`dotfiles/starship.toml`)**:
  - Alterada a diretiva `palette` de `"noctalia"` para `"asura"`.
  - Renomeada a seção de cores para `[palettes.asura]`.
  - Removidos cabeçalhos e comentários residuais alusivos a outros projetos.

- **Micro (`dotfiles/micro/`)**:
  - Removidos arquivos de histórico (`buffers/history`) e backups temporários (`backups/`) que continham dados de sessões antigas e referências residuais.

---

## 2. Associação Completa com o Matugen

Todos os dotfiles agora possuem integração e templates definidos para geração dinâmica de temas através do Matugen:

- **Centralização no Matugen (`dotfiles/matugen/config.toml`)**:
  - **Hyprland (`templates.hyprland`)**: Adicionada a declaração do template mapeando `hyprland-colors.lua` para `~/.config/hypr/scheme/current.lua` com hook `hyprctl reload`.
  - **Starship (`templates.starship`)**: Corrigido o caminho de entrada (estava configurado incorretamente como `.css`) para `starship-colors.toml`, gerando `~/.config/starship.toml`.
  - **Fish Shell (`templates.fish`)**: Adicionado template mapeando `fish-colors.fish` para `~/.config/fish/conf.d/matugen.fish`.
  - **Flameshot (`templates.flameshot`)**: Adicionado template mapeando `flameshot.ini` para `~/.config/flameshot/flameshot.ini`.
  - **Fastfetch (`templates.fastfetch`)**: Adicionado template mapeando `fastfetch.jsonc` para `~/.config/fastfetch/config.jsonc`.
  - **Cava (`templates.cava`)**: Adicionado template mapeando `cava-colors.ini` para `~/.config/cava/config` com sinal de recarregamento (`pkill -USR2 cava`).
  - **Neovim (`templates.nvim`)**: Adicionado template mapeando `nvim-colors.vim` para `~/.config/nvim/colors/asura.vim`.
  - **Quickshell (`templates.Asura`)**, **Kitty (`templates.kitty`)**, **BTOP (`templates.btop`)**, **Micro (`templates.micro`)**, **GTK 3/4** e **Vivaldi**: Mantidos e validados.

- **Template do Hyprland (`dotfiles/matugen/themes/hyprland-colors.lua`)**:
  - Reestruturado para gerar o formato correto de tabela Lua consumido pelas configurações do Hyprland (`hyprland.lua`, `variables.lua`, `hyprland/group.lua`, `hyprland/misc.lua`).
  - Fornece tanto as chaves em *snake_case* quanto os aliases em *camelCase* (`primary`, `inversePrimary`, `onPrimary`, `surfaceContainer`, `onSurfaceVariant`, `outline`, `secondary`, etc.), sem o prefixo rígido `0xff`, permitindo a correta formatação `rgba(...)` e `rgb(...)`.

- **Template do Starship (`dotfiles/matugen/themes/starship-colors.toml`)**:
  - Atualizado para a paleta `asura` com variáveis completas do Material You (`{{colors.*}}`) e todos os ícones e módulos correspondentes ao `starship.toml`.

- **Template e Configuração do Fish (`dotfiles/matugen/themes/fish-colors.fish` e `dotfiles/fish/conf.d/matugen.fish`)**:
  - Criado template para aplicar as cores do Material Design 3 na sintaxe do Fish.
  - Criado o arquivo padrão `matugen.fish` em `conf.d/` para funcionamento imediato mesmo antes da primeira execução do Matugen.

- **Template e Configuração do Flameshot (`dotfiles/matugen/themes/flameshot.ini` e `dotfiles/flameshot/flameshot.ini`)**:
  - Criado template parametrizado para `uiColor` e `contrastUiColor`.
  - Atualizado o arquivo padrão com as cores do Asura.

- **Template e Configuração do Fastfetch (`dotfiles/matugen/themes/fastfetch.jsonc` e `dotfiles/fastfetch/config.jsonc`)**:
  - Criado template parametrizado para as cores dos módulos, títulos e ícones.
  - Atualizado o `config.jsonc` padrão para refletir as cores do tema.

---

## 3. Remoção de Comentários em Português e Limpeza de Ruído

- **Vivaldi CSS (`dotfiles/matugen/themes/vivaldi.css` e `dotfiles/matugen/vivaldi/vivaldi.css`)**:
  - Removidos todos os blocos de comentários em português sobre regras da mainbar, opacidade e elementos de interface.

- **Hyprland (`dotfiles/hypr/hyprland/typescript`)**:
  - Removido arquivo de gravação de terminal de sessão antiga (`typescript`) que continha sequências de escape, comandos locais e comentários em português.

- **Micro (`dotfiles/micro/backups/`)**:
  - Removidos arquivos de backup contendo testes de texto em português e caminhos locais da máquina.

---

## 4. Generalização de Caminhos de Usuário

- **Fish (`dotfiles/fish/config.fish`)**:
  - Substituído caminho estático `/home/lucas/.spicetify` por `$HOME/.spicetify`.
  - Removida definição estática `set -g fish_color_command 84BCDA` para permitir controle dinâmico pelo Matugen.

- **Variáveis do Fish (`dotfiles/fish/fish_variables`)**:
  - Removida linha `fish_user_paths` contendo `/home/lucas/`, permitindo portabilidade para qualquer usuário e instalação em outras máquinas.
