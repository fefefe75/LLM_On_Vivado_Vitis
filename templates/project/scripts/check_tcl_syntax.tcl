#!/usr/bin/env tclsh
# =============================================================================
#  Verification de la SYNTAXE des scripts Tcl (Vivado / Vitis) - sans execution.
#
#  Usage :  tclsh scripts/check_tcl_syntax.tcl fichier1.tcl [fichier2.tcl ...]
#           (le Makefile racine l'appelle via : make tcl-check)
#
#  Ce que le script verifie, pour chaque fichier :
#    1. l'equilibrage global des accolades, crochets et guillemets
#       (info complete) : c'est la panne n°1 d'un script Tcl) ;
#    2. la compilation du script entier par Tcl : toute construction que le
#       compilateur refuse (par exemple du texte apres une accolade fermante)
#       est signalee.
#  En cas d'echec, un indice de localisation (ligne de l'accolade ou du
#  crochet reste ouvert) est affiche.
#
#  Ce que le script NE fait PAS (et ne peut pas faire) :
#    - il n'execute rien : les commandes Vivado/Vitis n'ont pas besoin
#      d'exister et aucun fichier du disque n'est touche ;
#    - il ne verifie pas la semantique (un nom de commande mal orthographie
#      passe l'analyse de syntaxe) ;
#    - les corps de 'proc' imbriques ne sont pas analyses si Tcl les compile
#      paresseusement (comportement de Tcl 9). Un script syntaxiquement valide
#      peut donc encore echouer a l'execution.
#
#  Code de sortie : 0 si tous les fichiers passent, 1 sinon, 2 si mauvais usage.
# =============================================================================

if {$argc == 0} {
    puts stderr "usage : tclsh $argv0 fichier1.tcl \[fichier2.tcl ...\]"
    exit 2
}

# ----------------------------------------------------------------------------
# Localisation approximative d'un desequilibre : renvoie une liste vide ou une
# phrase d'indice (ligne de l'accolade/crochet/guillemet non ferme).
# Analyse caractere par caractere, en ignorant les echappements et les
# commentaires Tcl (un # en debut de commande).
# ----------------------------------------------------------------------------
proc locate_imbalance {text} {
    set brace_stack {}
    set bracket_stack {}
    set quote_line 0
    set line 1
    set prev_significant " "
    set i 0
    set n [string length $text]

    while {$i < $n} {
        set c [string index $text $i]

        if {$c eq "\n"} { incr line; incr i; continue }

        if {$c eq "\\"} { incr i 2; continue }

        # commentaire : # en debut de commande
        # ATTENTION : a l'interieur d'un bloc d'accolades, Tcl compte les
        # accolades meme dans les commentaires et les chaines. Toute accolade
        # litterale doit donc etre echappee avec un antislash.
        if {$c eq "#" && ($prev_significant eq " " || $prev_significant eq "\n" || $prev_significant eq ";" || $prev_significant eq "\{" || $prev_significant eq "" )} {
            while {$i < $n && [string index $text $i] ne "\n"} { incr i }
            continue
        }

        if {$c eq "\""} {
            if {$quote_line == 0} { set quote_line $line } else { set quote_line 0 }
            incr i; set prev_significant $c; continue
        }

        if {$quote_line == 0} {
            switch -- $c {
                "\{" { lappend brace_stack $line }
                "\}" {
                    if {[llength $brace_stack] == 0} {
                        return "accolade fermante de trop a la ligne $line"
                    }
                    set brace_stack [lrange $brace_stack 0 end-1]
                }
                "\[" { lappend bracket_stack $line }
                "\]" {
                    if {[llength $bracket_stack] == 0} {
                        return "crochet fermant de trop a la ligne $line"
                    }
                    set bracket_stack [lrange $bracket_stack 0 end-1]
                }
            }
        }
        if {![string is space $c]} { set prev_significant $c }
        incr i
    }

    if {$quote_line != 0} { return "guillemet ouvert a la ligne $quote_line, jamais ferme" }
    if {[llength $brace_stack] != 0} {
        return "accolade ouverte a la ligne [lindex $brace_stack end], jamais fermee"
    }
    if {[llength $bracket_stack] != 0} {
        return "crochet ouvert a la ligne [lindex $bracket_stack end], jamais ferme"
    }
    return ""
}

# ----------------------------------------------------------------------------
set rc 0
set n_ok 0
set n_ko 0

foreach f $argv {
    if {![file exists $f]} {
        puts "  \[ECHEC\]   $f : fichier introuvable"
        incr n_ko
        set rc 1
        continue
    }

    set err ""
    set fh [open $f r]
    if {[catch {read $fh} body]} { set body "" ; set err "lecture impossible" }
    close $fh

    # --- 1. equilibrage global ----------------------------------------------
    if {$err eq "" && ![info complete $body]} {
        set err "script Tcl incomplet (accolade, crochet ou guillemet non equilibre)"
        set hint [locate_imbalance $body]
        if {$hint ne ""} { set err "$err -> $hint" }
    }

    # --- 2. compilation du script par Tcl (sans execution) ------------------
    if {$err eq ""} {
        if {[catch {proc ::__check_tcl_syntax__ {} $body} cerr]} {
            set err "syntaxe refusee par Tcl : $cerr"
        }
        # le proc jetable ne doit pas rester : on le supprime immediatement
        catch {rename ::__check_tcl_syntax__ ""}
    }

    if {$err eq ""} {
        puts "  \[OK\]      $f"
        incr n_ok
    } else {
        puts "  \[ECHEC\]   $f"
        puts "            $err"
        incr n_ko
        set rc 1
    }
}

puts ""
puts "  tcl-check : $n_ok fichier(s) valide(s), $n_ko en echec"
if {$rc != 0} {
    puts "  rappel : la syntaxe valide ne prouve pas que le script fera ce qu'on veut"
    puts "           (les commandes Vivado/Vitis ne sont pas verifiees ici)."
}
exit $rc
