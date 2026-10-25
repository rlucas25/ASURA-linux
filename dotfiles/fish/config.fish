if status is-interactive

    set -g fish_greeting    

    set -gx EDITOR micro
    set -gx VISUAL micro

    # CachyOS fish-done notification compatibility
    if not set -q __done_min_cmd_duration; or test -z "$__done_min_cmd_duration"
        set -g __done_min_cmd_duration 5000
    end

    fastfetch
    if command -v pacman >/dev/null 2>&1
        alias i 'sudo pacman -S'
        alias r 'sudo pacman -R'
        alias s 'sudo pacman -Q'
        alias up 'sudo pacman -Syu'
    else if command -v dnf >/dev/null 2>&1
        alias i 'sudo dnf install'
        alias r 'sudo dnf remove'
        alias s 'dnf list installed'
        alias up 'sudo dnf upgrade'
    end
    alias cd 'z'
    alias cat 'bat'
    alias rblue 'systemctl --user restart wireplumber pipewire pipewire-pulse && sudo systemctl restart bluetooth'
    if command -v starship >/dev/null 2>&1
        starship init fish | source
      end
    
    if command -v zoxide >/dev/null 2>&1
        zoxide init fish --cmd cd | source
    end
    
    # fzf walks the tree via fd when present.
    if command -v fd >/dev/null 2>&1
        set -gx FZF_DEFAULT_COMMAND 'fd --hidden --follow --exclude .git'
        set -gx FZF_CTRL_T_COMMAND $FZF_DEFAULT_COMMAND
        set -gx FZF_ALT_C_COMMAND 'fd --type d --hidden --follow --exclude .git'
    end
    
    # fzf keys: Ctrl-R history, Ctrl-T files, Alt-C cd.
    if command -v fzf >/dev/null 2>&1
        fzf --fish | source
    end
    
    # eza listings.
    if command -v eza >/dev/null 2>&1
        alias ls 'eza --group-directories-first --icons=auto'
        alias lsa 'ls -a'
        alias lt 'eza --tree --level=2 --long --icons --git'
        alias lta 'lt -a'
    end

end

fish_add_path "$HOME/.local/bin"

if test -d "$HOME/.spicetify"
    fish_add_path "$HOME/.spicetify"
end
