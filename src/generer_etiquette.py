#!/usr/bin/env python3
"""
Générateur d'étiquettes de danger (LaTeX + pictogrammes GHS)
--------------------------------------------------------------
Remplit le template "templates/etiquette_template.tex" via saisie
console, puis compile directement le PDF avec pdflatex.

Structure de projet attendue (ce script vit dans src/) :

  projet/
  ├── pictos/                 pictogrammes .png
  ├── templates/
  │   └── etiquette_template.tex
  ├── src/
  │   └── generer_etiquette.py   (ce fichier)
  ├── export_latex/            créé automatiquement — .tex générés
  └── export_pdf/               créé automatiquement — PDF générés

Aucun fichier n'est jamais écrit à la racine du projet :
  - le .tex final est écrit directement dans "export_latex/"
  - le PDF (et les fichiers auxiliaires .aux/.log, supprimés ensuite)
    sont écrits directement dans "export_pdf/" via l'option
    -output-directory de pdflatex

Prérequis :
  - une distribution LaTeX installée (pdflatex accessible dans le PATH)

Utilisation :
  python generer_etiquette.py
  (peut être lancé depuis n'importe quel dossier)
"""

import os
import subprocess
import sys
from pathlib import Path

# Dossier où se trouve ce script (src/), et racine du projet (son parent) :
# permet de lancer le script depuis n'importe où sans erreur de chemin.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
os.chdir(PROJECT_ROOT)

TEMPLATE_FILE = PROJECT_ROOT / "templates" / "etiquette_template.tex"
PICTOS_DIR = PROJECT_ROOT / "pictos"

# Dossiers de sortie dédiés (créés automatiquement s'ils n'existent pas)
EXPORT_PDF_DIR = PROJECT_ROOT / "export_pdf"
EXPORT_LATEX_DIR = PROJECT_ROOT / "export_latex"
EXPORT_PDF_DIR.mkdir(exist_ok=True)
EXPORT_LATEX_DIR.mkdir(exist_ok=True)

TAILLES_VALIDES = ["26mm", "50mm", "100mm"]

PICTOS_DISPONIBLES = [
    "explosif",
    "inflammable",
    "comburant",
    "gaz-sous-pression",
    "corrosif",
    "toxique-aigu",
    "nocif-irritant",
    "danger-grave-pour-la-sante",
    "dangereux-pour-environnement",
]


def escape_latex(texte: str) -> str:
    """Échappe les caractères spéciaux LaTeX les plus courants."""
    remplacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for ancien, nouveau in remplacements.items():
        texte = texte.replace(ancien, nouveau)
    return texte


def choisir_taille() -> str:
    print("\nTaille de l'étiquette :")
    for i, t in enumerate(TAILLES_VALIDES, 1):
        print(f"  {i}. {t}")
    while True:
        choix = input(f"Choix [1-{len(TAILLES_VALIDES)}] (défaut : 2 = 50mm) : ").strip()
        if choix == "":
            return "50mm"
        if choix.isdigit() and 1 <= int(choix) <= len(TAILLES_VALIDES):
            return TAILLES_VALIDES[int(choix) - 1]
        print("Choix invalide, réessayez.")


def choisir_texte() -> str:
    while True:
        texte = input("\nTexte de l'étiquette : ").strip()
        if texte:
            return texte
        print("Le texte ne peut pas être vide.")


def choisir_picto(numero: int) -> str:
    print(f"\nPictogramme {numero}/3 (laisser vide pour ne pas en mettre) :")
    for i, p in enumerate(PICTOS_DISPONIBLES, 1):
        print(f"  {i}. {p}")
    while True:
        choix = input(f"Choix [1-{len(PICTOS_DISPONIBLES)}] ou vide : ").strip()
        if choix == "":
            return ""
        if choix.isdigit() and 1 <= int(choix) <= len(PICTOS_DISPONIBLES):
            return PICTOS_DISPONIBLES[int(choix) - 1]
        print("Choix invalide, réessayez.")


def remplir_template(taille: str, texte: str, pictos: list) -> str:
    if not TEMPLATE_FILE.exists():
        sys.exit(f"Erreur : le fichier template '{TEMPLATE_FILE}' est introuvable.")

    contenu = TEMPLATE_FILE.read_text(encoding="utf-8")

    contenu = contenu.replace("{{TAILLE}}", taille)
    contenu = contenu.replace("{{TEXTE}}", escape_latex(texte))
    contenu = contenu.replace("${PICTO1}", pictos[0])
    contenu = contenu.replace("${PICTO2}", pictos[1])
    contenu = contenu.replace("${PICTO3}", pictos[2])

    # Chemin des pictogrammes rendu ABSOLU : comme le .tex final est écrit
    # dans export_latex/ (et non à côté des images), un chemin relatif
    # "./pictos/" ne pointerait plus vers le bon dossier au moment de la
    # compilation. On force donc pdflatex à toujours chercher les images
    # dans le dossier pictos/ du projet, quel que soit l'endroit où l'on
    # compile.
    ancien_graphicspath = r"\graphicspath{{./}{./pictos/}}"
    racine_abs = PROJECT_ROOT.as_posix() + "/"
    pictos_abs = PICTOS_DIR.as_posix() + "/"
    nouveau_graphicspath = (
        r"\graphicspath{{" + racine_abs + "}{" + pictos_abs + "}}"
    )
    contenu = contenu.replace(ancien_graphicspath, nouveau_graphicspath)

    return contenu


def compiler_pdf(tex_path: Path, nom_fichier: str):
    """Compile le .tex (situé dans export_latex/) en écrivant directement
    le résultat (PDF + fichiers auxiliaires) dans export_pdf/."""
    print(f"\nCompilation de {tex_path.name} ...")
    try:
        resultat = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                f"-output-directory={EXPORT_PDF_DIR}",
                str(tex_path),
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        sys.exit(
            "Erreur : 'pdflatex' est introuvable. "
            "Installez une distribution LaTeX (TeX Live / MiKTeX) et réessayez."
        )

    # Nettoyage des fichiers auxiliaires, qu'il y ait eu succès ou échec
    for ext in (".aux", ".log"):
        aux_file = EXPORT_PDF_DIR / f"{nom_fichier}{ext}"
        if aux_file.exists():
            aux_file.unlink()

    if resultat.returncode != 0:
        print("La compilation a rencontré des erreurs. Extrait du log :")
        print("\n".join(resultat.stdout.splitlines()[-25:]))
        sys.exit(1)

    pdf_final = EXPORT_PDF_DIR / f"{nom_fichier}.pdf"
    print(f"PDF généré : {pdf_final}")


def main():
    print("=== Générateur d'étiquette de danger ===")

    taille = choisir_taille()
    texte = choisir_texte()

    pictos = []
    for i in (1, 2, 3):
        pictos.append(choisir_picto(i))

    contenu_final = remplir_template(taille, texte, pictos)

    nom_sortie = input(
        "\nNom du fichier de sortie (sans extension) [défaut : etiquette] : "
    ).strip() or "etiquette"

    # Le .tex final est écrit DIRECTEMENT dans export_latex/ : jamais de
    # fichier temporaire à la racine du dossier du script.
    tex_final = EXPORT_LATEX_DIR / f"{nom_sortie}.tex"
    tex_final.write_text(contenu_final, encoding="utf-8")
    print(f"Fichier LaTeX généré : {tex_final}")

    compiler_pdf(tex_final, nom_sortie)


if __name__ == "__main__":
    main()
