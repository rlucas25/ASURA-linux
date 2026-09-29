# Planejamento do Instalador e CLI ASURA

Este documento define a arquitetura, estrutura de diretórios, escolha de tecnologias e o passo a passo para a criação do instalador e utilitário CLI do **ASURA**, com suporte inicial planejado para **Arch Linux** (e derivados como CachyOS/EndeavourOS) e **Fedora Linux**.

---

## 1. Avaliação e Refinamento do `pastas.md`

Sua ideia de centralizar os arquivos e usar links simbólicos é a melhor prática no ecossistema Linux. No entanto, algumas pastas podem ser otimizadas para seguir o padrão **XDG Base Directory** e evitar conflitos com outros programas.

### Análise Crítica da Proposta Atual

| Proposta em `pastas.md` | Avaliação | Recomendação Técnica |
| :--- | :--- | :--- |
| `/home/$USER/Pictures/...` | O caminho rígido `/home/$USER` quebra se o usuário tiver `HOME` customizado. | Utilizar `$HOME` ou comandos XDG (`xdg-user-dir PICTURES`). |
| `~/.local/share/ASURA` | Excelente escolha para armazenar os fontes da shell e repositório. | Padronizar em minúsculas: `~/.local/share/asura` (convenção Linux). |
| `~/.config/dots` | Nome muito genérico; pode colidir com outros gerenciadores (ex: Stow, Chezmoi). | Mover para `~/.local/share/asura/dotfiles` (fonte) ou `~/.config/asura/dots`. |
| `~/.config/Backup` | Criar pasta solta em maiúsculo no `.config` quebra padrões e fica desorganizada. | Estruturar como `~/.config/asura/backups/<TIMESTAMP>/` ou `~/.local/state/asura/backups/`. |
| `~/.config/asura` | **Excelente**. Perfeito para configurações do usuário (`hypr-user.lua`, `hypr-vars.lua`, `config.json`). | Manter como pasta principal de configurações de runtime do usuário. |

### Estrutura Final Recomendada

```text
$HOME/
├── .config/
│   ├── asura/                      # Configurações do usuário e estado local
│   │   ├── config.json             # Preferências da shell e temas
│   │   ├── hypr-vars.lua           # Overrides de variáveis do Hyprland
│   │   ├── hypr-user.lua           # Configurações extras do Hyprland do usuário
│   │   └── backups/                # Backups automáticos versionados por data/hora
│   │       └── 2026-09-28_23-15-00/
│   │           ├── hypr/
│   │           └── kitty/
│   ├── hypr/ -> ~/.local/share/asura/dotfiles/hypr          # Link simbólico
│   ├── kitty/ -> ~/.local/share/asura/dotfiles/kitty        # Link simbólico
│   ├── btop/ -> ~/.local/share/asura/dotfiles/btop          # Link simbólico
│   ├── matugen/ -> ~/.local/share/asura/dotfiles/matugen    # Link simbólico
│   └── starship.toml -> ~/.local/share/asura/dotfiles/starship.toml
├── .local/
│   ├── bin/
│   │   └── asura                   # Executável do CLI disponível no terminal ($PATH)
│   └── share/
│       └── asura/                  # Repositório clonado (código-fonte + shell + dots)
│           ├── .git/
│           ├── Asura-shell/
│           ├── dotfiles/
│           └── cli/
└── Pictures/
    ├── Wallpapers/
    └── Screenshots/
```

---

## 2. Escolha da Linguagem: Por que Python 3?

Para um instalador moderno com CLI (`asura run`, `asura update`), **Python 3** é a linguagem mais recomendada para esse cenário.

### Comparativo

| Critério | Shell Script (Bash) | Python 3 (Padrão) | Rust / Go |
| :--- | :--- | :--- | :--- |
| **Disponibilidade** | Nativo | Nativo em Arch e Fedora sem instalar nada extra | Exige compilação prévia ou toolchain |
| **Parsing de JSON/TOML** | Depende de `jq`, frágil com regex | Módulo `json` embutido nativo | Rápido, mas requer dependências externas |
| **Subcomandos CLI** | Complexo de manter (`case "$1"`) | Módulo nativo `argparse` muito simples | Excelente (`clap`), mas compilação demorada |
| **Backup & Links** | Comandos `ln`, `cp` via shell | `shutil`, `os.path`, `pathlib.Path.symlink_to` | Nativo |
| **Multi-distro** | Muitos `if/else` e subprocessos soltos | Dicionários declarativos limpos por distro | Bom, mas verboso |

---

## 3. Abstração Multi-Distro (Arch vs Fedora)

O instalador precisa identificar a distro lendo `/etc/os-release` e mapear os nomes de pacotes equivalentes.

### Tabela de Mapeamento de Pacotes

| Componente | Arch Linux / CachyOS (`pacman` / AUR) | Fedora Linux (`dnf` / Copr) |
| :--- | :--- | :--- |
| Gerenciador | `pacman -S --needed` / `yay` / `paru` | `dnf install -y` |
| Compositor | `hyprland` | `hyprland` |
| Quickshell | `quickshell` (AUR/git) | `quickshell` (Copr ou compilação) |
| Matugen | `matugen-bin` (AUR) | `matugen` (Copr ou cargo) |
| Terminal | `kitty` | `kitty` |
| Shell | `fish` | `fish` |
| Prompt | `starship` | `starship` |
| Monitor de Sistema | `btop` | `btop` |
| Screenshots | `flameshot` | `flameshot` |
| Informações | `fastfetch` | `fastfetch` |
| Polkit & Keyring | `polkit-gnome`, `gnome-keyring` | `polkit-gnome`, `gnome-keyring` |
| Wallpaper Daemon | `awww` (AUR) / `swww` | `swww` (Copr) |

---

## 4. Estratégia de Backup Inteligente

Antes de aplicar qualquer link simbólico ou copiar arquivos, o instalador deve inspecionar os alvos em `~/.config/`.

### Regras do Backup
1. **Verificação de Alvo**: Se o diretório/arquivo de destino já existir (ex: `~/.config/hypr`):
   - Se for um link simbólico apontando para o próprio ASURA: ignora (já instalado).
   - Se for uma pasta ou link para outro local: adiciona à lista de backup.
2. **Criação do Diretório de Backup**:
   - `~/.config/asura/backups/backup_YYYYMMDD_HHMMSS/`
3. **Mover em vez de Sobrescrever**:
   - Move com segurança preservando permissões (`shutil.move`).
4. **Log do Backup**:
   - Gera um arquivo `manifest.json` dentro da pasta de backup informando a origem de cada item para possibilitar reversão/restauração futura (`asura rollback`).

---

## 5. Arquitetura do CLI (`asura`)

O CLI será o ponto de contato do usuário após a instalação. Ao instalar, o script cria um link simbólico:
`~/.local/bin/asura -> ~/.local/share/asura/cli/main.py` (com permissão de execução `+x`).

### Comandos Planejados

- `asura run`: Inicia a shell quickshell (`qs -d`) e componentes necessários.
- `asura reload`: Recarrega Hyprland (`hyprctl reload`) e reinicia a Quickshell.
- `asura update`: Atualiza o ASURA via Git e aplica novas configs.
- `asura theme`: Aplica wallpaper e roda o matugen para gerar novas cores.
- `asura backup`: Faz backup manual das configurações atuais.
- `asura rollback`: Restaura o último backup disponível.
- `asura doctor`: Diagnóstico de dependências e estado dos serviços.

### Detalhamento dos Comandos Principais

#### 1. `asura run`
- Verifica se a sessão Wayland/Hyprland está ativa.
- Dispara `awww-daemon` (se não estiver rodando).
- Dispara `qs -d` (Quickshell).

#### 2. `asura reload`
- Executa `hyprctl reload`.
- Envia comando IPC para Quickshell (`pkill qs; sleep 0.2; qs -d &`).
- Recarrega Matugen no wallpaper atual se necessário.

#### 3. `asura update` (Gerenciamento de Atualizações)
O fluxo padrão de atualização funciona assim:
1. Conecta ao repositório git local em `~/.local/share/asura`.
2. Faz `git fetch origin`.
3. Compara `HEAD` local com `origin/main`. Se não houver novos commits, avisa que já está atualizado.
4. Se houver novos commits:
   - Faz backup de segurança do estado atual.
   - Aplica `git pull --rebase origin main`.
   - Verifica se novos dotfiles foram criados no repositório e cria os links simbólicos correspondentes.
   - Roda o Matugen para atualizar os esquemas de cores.
   - Chama `asura reload` para aplicar sem reiniciar o sistema.

---

## 6. Passo a Passo de Implementação Sugerido

### Fase 1: Estruturar a Pasta do Projeto
Organizar o repositório atual para acomodar o instalador e o CLI:
- `dotfiles/`: os arquivos de configuração (já limpos e preparados).
- `Asura-shell/`: a interface Quickshell.
- `cli/`: código do utilitário `asura` (`main.py`, `commands/`).
- `install.sh`: script de entrada com comando de uma linha (`curl | bash`).

### Fase 2: Criar o Módulo do CLI (`cli/`)
Criar o CLI unificado com `argparse`:
- Suporte a `asura --help`
- Implementar `asura reload` e `asura run`
- Implementar `asura doctor` (checa se `hyprland`, `matugen`, `quickshell`, `kitty` estão instalados).

### Fase 3: Criar o Instalador
- Detecção da distro (`/etc/os-release`).
- Instalação de pacotes via `pacman`/`yay` ou `dnf`.
- Rotina de backup e criação dos links simbólicos.
- Vinculação do binário `asura` em `~/.local/bin/asura`.

### Fase 4: Criar o Sistema de Atualização (`asura update`)
- Implementar rotinas do `git pull`.
- Garantir que modificações em `~/.config/asura/hypr-user.lua` nunca sejam sobrescritas.


### Fase 5: Versionamento e Estratégia de Dependências
- **Classificação dos 3 Níveis**:
  1. *Utilitários de Sistema* (DNF / Pacman): `kitty`, `fish`, `starship`, `btop`, `micro`, `flameshot`, `fastfetch`.
  2. *Compositor Wayland* (COPR `solopasha/hyprland` / Pacman): `hyprland`, `hypridle`, `xdg-desktop-portal-hyprland`.
  3. *Ferramentas Críticas de Tema* (GitHub Releases / Binários diretos): `matugen`, `quickshell`.
- **Garantia de Versão (Exemplo do Matugen 4.2.0)**:
  Baixar o binário pré-compilado oficial em `~/.local/bin/matugen` se a versão da distro for defasada.
