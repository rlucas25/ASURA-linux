# Guia Definitivo: Construção de Instaladores, Ferramentas CLI e Dotfiles para Linux

Este guia foi elaborado para quem já compreende lógica de programação e Python, mas deseja dominar o desenvolvimento de **automações de sistema, instaladores de dotfiles, utilitários CLI e arquitetura no ecossistema Linux**.

---

## Sumário e Mapa de Estudos Essenciais

Antes de escrever código, você precisa entender como os componentes do Linux conversam entre si. Este mapa lista os conceitos indispensáveis organizados por área:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      MAPA DE ESTUDOS ESSENCIAIS                        │
├────────────────────────────────┬───────────────────────────────────────┤
│ 1. Fundamentos de Linux        │ • Padrão XDG Base Directory           │
│                                │ • Resolução de binários e PATH        │
│                                │ • Shebangs e Permissões POSIX         │
│                                │ • Links Simbólicos vs Hard Links      │
├────────────────────────────────┼───────────────────────────────────────┤
│ 2. Python para Automação       │ • pathlib.Path (Manipulação moderna)  │
│                                │ • subprocess.run (Execução segura)    │
│                                │ • argparse (Criação de CLIs)          │
│                                │ • Idempotência e Tratamento de Erros  │
├────────────────────────────────┼───────────────────────────────────────┤
│ 3. Ambientes de Teste          │ • Containers (Distrobox / Podman)     │
│                                │ • Máquinas Virtuais (QEMU / Quickemu) │
│                                │ • Snapshots de Sistema                │
├────────────────────────────────┼───────────────────────────────────────┤
│ 4. Serviços e Sistema          │ • systemd --user vs Hyprland exec     │
│                                │ • D-Bus e IPC                         │
│                                │ • Gerenciamento de Energia            │
├────────────────────────────────┼───────────────────────────────────────┤
│ 5. Arquitetura de Dotfiles     │ • Split Configs e Overrides           │
│                                │ • Atualizações Seguras via Git        │
│                                │ • Documentação e Auto-diagnóstico     │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 1. Como Funcionam os Componentes no Linux

Muitos desenvolvedores usam comandos sem saber o que o Linux faz internamente. Entender esses mecanismos evita erros clássicos em instaladores.

### A. O que acontece quando você digita `asura run` no terminal?

Quando você digita qualquer palavra no terminal (como `asura`, `python3` ou `kitty`), o sistema executa o seguinte fluxo:

1. **A variável `$PATH`:** A shell (Bash, Fish ou Zsh) não procura em todo o disco. Ela consulta a variável de ambiente `$PATH`, que é uma lista de pastas separadas por dois-pontos:
   ```text
   /usr/local/bin : /usr/bin : /bin : /home/usuario/.local/bin
   ```
2. **A busca linear:** A shell verifica pasta por pasta na ordem exata até encontrar um arquivo executável com o nome `asura`.
3. **Por que `~/.local/bin` é o local ideal para o instalador?**
   * Pastas como `/usr/bin` pertencem exclusivamente ao gerenciador de pacotes da distribuição (DNF, Pacman).
   * Pastas como `/usr/local/bin` exigem privilégios de `root` (`sudo`) para escrever.
   * `~/.local/bin` é o padrão **XDG** para binários do usuário comum. Quase todas as distribuições modernas já o incluem no `$PATH` do usuário.
4. **O Shebang (`#!`):** Ao encontrar o arquivo, o Kernel do Linux lê os primeiros 2 bytes. Se começarem com `#!`, ele chama o interpretador especificado:
   * `#!/usr/bin/env python3` ➔ O Kernel pede para o comando `env` localizar o Python correto do sistema e passar o script como argumento.
5. **A Permissão de Execução (`chmod +x`):** No Linux, a extensão `.py` ou `.sh` não define se um arquivo pode rodar. O bit `x` (executable) nos metadados do arquivo é o que autoriza o Kernel a disparar o processo.
6. **O poder do Link Simbólico:**
   Se você colocar um link simbólico:
   `~/.local/bin/asura` ➔ apontando para `~/.local/share/asura/cli/main.py`
   **Qualquer alteração que você fizer no código do repositório reflete no terminal instantaneamente**, sem precisar reinstalar ou recompilar!

---

### B. Daemons e Serviços: `systemd --user` vs Hyprland `exec-once`

Um instalador precisa saber onde colocar cada processo para iniciar junto com o sistema:

| Tipo | Onde Rodar | Exemplo | Por quê? |
| :--- | :--- | :--- | :--- |
| **Sessão Gráfica** | Hyprland `exec-once` | `awww-daemon`, `qs -d` | Devem iniciar e morrer junto com a sessão do Wayland. Se o Hyprland reiniciar, eles reiniciam. |
| **Serviço de Fundo (Headless)** | `systemd --user` | `pipewire`, `cliphist` | Continuam ativos mesmo se o compositor gráfico cair ou trocar de sessão. |

---

## 2. Ambientes de Teste: Containers vs Máquinas Virtuais (QEMU)

Testar seu instalador formatando a máquina física é lento, desgastante e arriscado. Para desenvolver com agilidade, você precisa de ambientes isolados descartáveis.

### Diferença Conceitual

| Característica | Container (Distrobox / Podman) | Máquina Virtual (QEMU / Quickemu) |
| :--- | :--- | :--- |
| **Arquitetura** | Compartilha o mesmo Kernel do sistema host. | Virtualiza hardware completo (Kernel próprio, BIOS, GPU virtual). |
| **Inicialização** | Quase instantânea (1 a 2 segundos). | Mais lenta (15 a 45 segundos para boot do SO). |
| **Uso de Recursos** | Mínimo (apenas os processos que você rodar). | Alto (aloca RAM, vCPU e disco fixos). |
| **Systemd / Daemons** | Limitado (containers padrão não rodam init completo). | Completo (roda `systemd`, `systemctl`, display managers). |
| **Interface Gráfica** | Roda apps GUI compartilhando o Wayland/X11 do host. | Roda sessões completas do Hyprland do zero. |
| **Caso de Uso Ideal** | **Testar pacotes, links simbólicos, Python e scripts CLI.** | **Testar boot do sistema, login e compositor Wayland.** |

---

### Setup Prático 1: Distrobox (Para testes ultra-rápidos de scripts)

O **Distrobox** usa Podman ou Docker por baixo dos panos, mas integra seu usuário, terminal e arquivos de forma transparente. É a melhor ferramenta para testar seu instalador no Fedora sem sair do Arch/CachyOS.

#### Instalação no Arch/CachyOS:
```bash
sudo pacman -S distrobox podman
```

#### Criando e usando um container Fedora limpo:
```bash
# 1. Cria um container com Fedora puro (baixa a imagem oficial)
distrobox create -i fedora:latest -n teste-fedora

# 2. Entra no container (leva 2 segundos)
distrobox enter teste-fedora

# 3. Agora você está dentro de um Fedora! Teste seus comandos:
sudo dnf install -y kitty fish
python3 --version

# 4. Para sair do container e voltar ao seu sistema principal:
exit
```

#### Para resetar ou apagar o container de teste:
```bash
distrobox rm -f teste-fedora
```

---

### Setup Prático 2: Quickemu (Para testar o Hyprland completo)

Se você precisa ver se o Hyprland vai iniciar, abrir a tela de login e renderizar a barra Quickshell no Fedora, use o **Quickemu** (baseado em QEMU/KVM com aceleração gráfica ativada por padrão).

#### Instalação no Arch/CachyOS:
```bash
sudo pacman -S quickemu edk2-ovmf
```

#### Subindo o Fedora em uma VM:
```bash
# Baixa automaticamente a ISO oficial do Fedora e configura a VM
quickget fedora 41

# Executa a máquina virtual com aceleração
quickemu --vm fedora-41.conf
```

> [!TIP]
> **Dica de Ouro (Snapshots):** Antes de rodar o seu instalador pela primeira vez na VM, tire um snapshot. Se o script quebrar o sistema, você volta ao estado original em 1 segundo sem reinstalar nada.

---

## 3. Dicas de Código e Sintaxe em Python para Scripts de Sistema

Programar scripts de sistema em Python exige cuidados específicos. Aqui estão os padrões que diferenciam um script amador de um profissional:

### A. Manipulação de Caminhos com `pathlib.Path` (Abandone `os.path`)

`pathlib.Path` trata caminhos como objetos ricos em métodos, facilitando operações de filesystem:

```python
from pathlib import Path

# Obtém a pasta home do usuário de forma segura
home = Path.home()

# Constrói caminhos com o operador /
config_dir = home / ".config" / "asura"
dotfiles_dir = home / ".local" / "share" / "asura" / "dotfiles"

# Cria diretórios recursivamente (equivalente a mkdir -p)
config_dir.mkdir(parents=True, exist_ok=True)

# Trabalhando com links simbólicos
origem = dotfiles_dir / "kitty"
destino = home / ".config" / "kitty"

# Inspeção segura
if destino.is_symlink():
    print(f"O link aponta para: {destino.resolve()}")
elif destino.exists():
    print("É uma pasta ou arquivo real do usuário!")
```

---

### B. Execução Segura com `subprocess.run` (Evite `shell=True`)

Muitos iniciantes usam `os.system()` ou `subprocess.run("comando", shell=True)`. Isso é vulnerável a injeção e falha com espaços em nomes de pastas.

```python
import subprocess
import shutil

# 1. Verificar se um utilitário existe no sistema antes de rodar
if shutil.which("hyprctl"):
    try:
        # Passa lista de strings: o primeiro elemento é o binário, o resto são argumentos
        subprocess.run(["hyprctl", "reload"], check=True)
        print("✔ Hyprland recarregado.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao recarregar Hyprland: {e}")

# 2. Capturar a saída de um comando (ex: versão)
resultado = subprocess.run(
    ["matugen", "--version"], 
    capture_output=True, 
    text=True, 
    check=True
)
print(f"Versão detectada: {resultado.stdout.strip()}")
```

---

### C. A Regra de Ouro do `sudo`: Não execute o instalador como root!

> [!CAUTION]
> **NUNCA peça para o usuário rodar:** `sudo python3 install.py`!
> Se o instalador rodar sob `sudo`, `Path.home()` pode apontar para `/root`, e qualquer arquivo criado em `~/.config/` pertencerá ao usuário `root:root`, travando o sistema do usuário comum após a reinicialização!

#### A Abordagem Correta:
O script roda com **permissões de usuário comum**. Apenas as chamadas que realmente exigem root (como `dnf install` ou `pacman -S`) recebem `sudo`:

```python
import subprocess

def instalar_pacotes(pacotes: list[str], gerenciador: str):
    if gerenciador == "dnf":
        cmd = ["sudo", "dnf", "install", "-y"] + pacotes
    elif gerenciador == "pacman":
        cmd = ["sudo", "pacman", "-S", "--needed", "--noconfirm"] + pacotes
    
    print(f"Executando: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
```

---

### D. Idempotência na Prática

> **Idempotência** significa: *Executar o seu instalador 1 vez ou 10 vezes consecutivas deve produzir exatamente o mesmo resultado, sem duplicar arquivos, quebrar links ou gerar erros.*

```python
from pathlib import Path

def link_seguro(origem: Path, destino: Path):
    """Cria link simbólico idempotente com segurança."""
    if destino.is_symlink():
        if destino.resolve() == origem.resolve():
            # Link correto já existe; não toca
            return
        destino.unlink() # Aponta para local errado; recria
    elif destino.exists():
        raise FileExistsError(f"Arquivo real existe em {destino}, faça backup antes!")

    destino.symlink_to(origem)
    print(f"✔ Link criado: {destino} -> {origem}")
```

---

### E. Sistema de Log Simples e Profissional

Quando um usuário relatar no GitHub: *"O instalador falhou no meu Fedora"*, você não precisa adivinhar. Crie um arquivo de log durante a execução:

```python
import logging
from pathlib import Path

log_dir = Path.home() / ".local" / "state" / "asura"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "installer.log"

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info("Instalador iniciado com sucesso.")
```

---

## 4. O Dilema dos Gerenciadores de Energia e Manutenção a Longo Prazo

No seu teste com o Fedora, surgiu a dúvida: *devo instalar o `power-profiles-daemon`, usar o `tuned`, ou deixar o usuário escolher?*

### O Cenário no Linux Atual
* **`power-profiles-daemon` (PPD):** O padrão tradicional do GNOME e KDE. Simples (Performance, Balanced, Power-saver). Controlado via D-Bus por interfaces gráficas.
* **`tuned` (com `tuned-ppd`):** O padrão recente do Fedora. Mais poderoso, com suporte a dezenas de perfis corporativos e otimizações avançadas de CPU/bateria.
* **`tlp`:** Muito popular entre usuários do Arch, mas frequentemente entra em conflito direto com o PPD ou o Tuned.

### Por que NÃO vale a pena forçar uma troca no sistema do usuário?
1. Se o usuário estiver no Fedora com `tuned` já otimizado para o hardware dele (ex: ThinkPads e laptops ASUS ROG), forçar a remoção e instalar o `power-profiles-daemon` pode **aumentar o consumo de bateria e quebrar daemons do fabricante**.
2. No Arch, muitos usuários usam `tlp` e não querem o PPD instalado.

### A Solução Arquitetural Profissional: Detecção Dinâmica
Em vez de desinstalar ou substituir o gerenciador do usuário, o instalador e a sua interface Quickshell devem **detectar o que está disponível**:

```python
import subprocess
import shutil

def get_power_backend():
    """Detecta qual gerenciador de energia está presente no sistema."""
    if shutil.which("powerprofilesctl"):
        return "power-profiles-daemon"
    elif shutil.which("tuned-adm"):
        return "tuned"
    elif shutil.which("tlp"):
        return "tlp"
    return "none"
```
* **Na Quickshell:** O widget de bateria/performance apenas consulta o D-Bus do serviço que estiver ativo.
* **No Instalador:** Se nenhum estiver presente, sugere ou instala o padrão mais simples (`power-profiles-daemon`), mas **se outro já estiver ativo, mantém o do usuário**.

---

## 5. Como Criar Documentação Profissional para o Projeto

Um bom projeto open-source é avaliado em 80% pela clareza da sua documentação.

### A. Estrutura Padrão de um `README.md` de Sucesso
1. **Hero Header:** Nome do projeto, logotipo e uma frase curta de impacto.
2. **Screenshots / GIF Animado:** Ninguém instala uma interface gráfica sem ver como ela se parece em funcionamento.
3. **Destaques (Features):** Lista concisa dos diferenciais (Material You, Quickshell, Integração Matugen, Leveza).
4. **Instalação Rápida (1 linha):**
   ```bash
   bash <(curl -s https://raw.githubusercontent.com/seu-user/asura/main/install.sh)
   ```
5. **Tabela de Atalhos de Teclado (Keybindings):** Tabela clara com os atalhos principais (`Super + A`, `Super + Enter`, `Super + V`).
6. **Guia de Customização:** Explicando onde o usuário pode alterar cores, variáveis e configs sem quebrar atualizações.
7. **Troubleshooting / FAQ:** Soluções para problemas comuns (ex: tela preta, áudio sem funcionar).

### B. Ajuda Embutida no Terminal (`asura --help`)
O próprio CLI deve ser autoexplicativo:
```text
$ asura --help
Uso: asura <comando> [opções]

Comandos:
  run       Inicia o daemon de wallpaper e a shell Quickshell
  reload    Recarrega configurações do Hyprland e Quickshell
  update    Atualiza o repositório e recompila temas com segurança
  theme     Aplica novo wallpaper e recalcula cores via Matugen
  doctor    Diagnostica dependências e integridade do sistema
```

### C. O Comando `asura doctor` (O salvador de suporte)
Implementar um comando de auto-diagnóstico reduz seus problemas de suporte no GitHub em até 80%:
```text
$ asura doctor
✔ Sessão Wayland ativa: Hyprland v0.45.0
✔ Quickshell encontrado em /usr/bin/quickshell
✔ Matugen compatível: v4.2.0
✔ Kitty terminal instalado
✔ Links simbólicos em ~/.config: Todos íntegros
```

---

## 6. Como Manter Dotfiles Base que Ainda Sejam Customizáveis

O maior pesadelo de quem cria dotfiles é: **como atualizar as configurações no futuro (`git pull`) sem sobrescrever as alterações que o usuário fez localmente?**

Aqui estão as 4 soluções consagradas para resolver isso:

### Solução 1: O Padrão "Split Config" (Overrides Separados do Git) - *Recomendado para o ASURA*
É exatamente a arquitetura que já estruturamos nas suas configs do Hyprland:
1. `hyprland.lua` (Controlado pelo Git): Contém a base da interface, regras gerais e lógica de carregamento.
2. `~/.config/asura/hypr-user.lua` (Nunca entra no Git): O arquivo é criado vazio na primeira instalação. O `hyprland.lua` faz:
   ```lua
   pcall(require, "hypr-user")
   ```
3. `~/.config/asura/hypr-vars.lua` (Nunca entra no Git): Contém tabelas de substituição (ex: usuário prefere trocar o atalho de terminal de Kitty para Alacritty, ou mudar o tamanho das bordas).

*Resultado:* Você pode atualizar o `hyprland.lua` via `git pull` 100 vezes que as preferências do usuário jamais serão apagadas.

---

### Solução 2: O Padrão "Drop-in Directory" (`.d`)
Popularizado pelo systemd e pelo Fish Shell:
* O sistema fornece a pasta padrão `~/.config/fish/conf.d/`.
* O ASURA coloca seus arquivos (ex: `matugen.fish`).
* O usuário pode criar seus próprios arquivos (ex: `meus-aliases.fish`).
* Ao atualizar o ASURA, apenas os arquivos do ASURA são tocados.

Para ferramentas que suportam inclusão (como o Kitty e Hyprland):
No `kitty.conf`:
```conf
include current-theme.conf
include ~/.config/asura/kitty-user.conf
```

---

### Solução 3: Separação de Tokens Visuais (Matugen)
Nunca misture regras lógicas com regras de cores:
* As cores ficam em arquivos dedicados gerados pelo Matugen (`Asura.conf`, `colors.json`, `scheme/current.lua`).
* O layout e comportamento ficam em arquivos estáticos.
* Assim, quando o usuário troca o wallpaper, apenas os arquivos de cores são regerados, sem tocar nas preferências de atalhos e janelas.

---

### Solução 4: Symlinks Granulares vs Symlink de Pasta Inteira
* ❌ **Evite:** Criar um link simbólico da pasta inteira `~/.config` para o repositório.
* ✔ **Recomendado:** Criar links específicos por aplicativo:
  * `~/.config/hypr` ➔ `~/.local/share/asura/dotfiles/hypr`
  * `~/.config/kitty` ➔ `~/.local/share/asura/dotfiles/kitty`
  * `~/.config/btop` ➔ `~/.local/share/asura/dotfiles/btop`
Dessa forma, o usuário continua com total liberdade para instalar e configurar outros softwares no seu sistema sem interferência do ASURA.
