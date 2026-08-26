#!/usr/bin/env python3
"""
Générateur d'étiquettes de danger — Interface graphique (Tkinter)
--------------------------------------------------------------------
Version graphique du générateur d'étiquettes LaTeX.
Aucune dépendance externe : utilise uniquement la bibliothèque standard
Python (tkinter est fourni avec l'installateur officiel python.org).

Structure de projet attendue (ce script vit dans src/) :

  projet/
  ├── pictos/                 pictogrammes .png
  ├── templates/
  │   └── etiquette_template.tex
  ├── src/
  │   └── generer_etiquette_gui.py   (ce fichier)
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
  python generer_etiquette_gui.py
  (peut être lancé depuis n'importe quel dossier)
"""

import os
import subprocess
import sys
import threading
import queue
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

# Dossier où se trouve ce script (src/), et racine du projet (son parent) :
# permet de le lancer depuis n'importe où sans erreur de chemin.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
os.chdir(PROJECT_ROOT)

TEMPLATE_FILE = PROJECT_ROOT / "templates" / "etiquette_template.tex"
PICTOS_DIR = PROJECT_ROOT / "pictos"

EXPORT_PDF_DIR = PROJECT_ROOT / "export_pdf"
EXPORT_LATEX_DIR = PROJECT_ROOT / "export_latex"
EXPORT_PDF_DIR.mkdir(exist_ok=True)
EXPORT_LATEX_DIR.mkdir(exist_ok=True)

TAILLES_VALIDES = ["26mm", "50mm", "100mm"]
PICTO_LABEL_AUCUN = "— Aucun —"
PICTOS_DISPONIBLES = [
    PICTO_LABEL_AUCUN,
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


def construire_contenu(taille: str, texte: str, pictos: list) -> str:
    if not TEMPLATE_FILE.exists():
        raise FileNotFoundError(f"Le fichier template '{TEMPLATE_FILE}' est introuvable.")

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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Générateur d'étiquettes de danger")
        self.resizable(False, False)
        self.log_queue = queue.Queue()

        self._construire_interface()
        self._verifier_prerequis()
        self.after(100, self._traiter_queue)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------
    def _construire_interface(self):
        pad = {"padx": 10, "pady": 6}

        main = ttk.Frame(self, padding=15)
        main.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            main,
            text="Générateur d'étiquettes de danger",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, columnspan=2, pady=(0, 15), sticky="w")

        # Taille
        ttk.Label(main, text="Taille de l'étiquette :").grid(row=1, column=0, sticky="w", **pad)
        self.var_taille = tk.StringVar(value=TAILLES_VALIDES[1])
        ttk.Combobox(
            main, textvariable=self.var_taille, values=TAILLES_VALIDES,
            state="readonly", width=25,
        ).grid(row=1, column=1, sticky="w", **pad)

        # Texte
        ttk.Label(main, text="Texte de l'étiquette :").grid(row=2, column=0, sticky="w", **pad)
        self.var_texte = tk.StringVar()
        entry_texte = ttk.Entry(main, textvariable=self.var_texte, width=35)
        entry_texte.grid(row=2, column=1, sticky="w", **pad)
        entry_texte.focus()

        # Pictogrammes (3 slots)
        self.vars_pictos = []
        for i in range(3):
            ttk.Label(main, text=f"Pictogramme {i + 1} :").grid(row=3 + i, column=0, sticky="w", **pad)
            var = tk.StringVar(value=PICTO_LABEL_AUCUN)
            ttk.Combobox(
                main, textvariable=var, values=PICTOS_DISPONIBLES,
                state="readonly", width=32,
            ).grid(row=3 + i, column=1, sticky="w", **pad)
            self.vars_pictos.append(var)

        # Nom du fichier
        ttk.Label(main, text="Nom du fichier :").grid(row=6, column=0, sticky="w", **pad)
        self.var_nom = tk.StringVar(value="etiquette")
        ttk.Entry(main, textvariable=self.var_nom, width=35).grid(row=6, column=1, sticky="w", **pad)

        # Bouton générer
        self.btn_generer = ttk.Button(main, text="Générer le PDF", command=self._lancer_generation)
        self.btn_generer.grid(row=7, column=0, columnspan=2, pady=(12, 5), sticky="ew")

        # Boutons ouvrir dossiers
        frame_btns = ttk.Frame(main)
        frame_btns.grid(row=8, column=0, columnspan=2, sticky="ew")
        ttk.Button(
            frame_btns, text="Ouvrir dossier PDF",
            command=lambda: self._ouvrir_dossier(EXPORT_PDF_DIR),
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ttk.Button(
            frame_btns, text="Ouvrir dossier LaTeX",
            command=lambda: self._ouvrir_dossier(EXPORT_LATEX_DIR),
        ).pack(side="left", expand=True, fill="x")

        # Zone de journal
        ttk.Label(main, text="Journal :").grid(row=9, column=0, sticky="w", pady=(15, 0))
        self.txt_log = tk.Text(
            main, width=55, height=10, state="disabled",
            bg="#111111", fg="#33ff33", font=("Consolas", 9),
        )
        self.txt_log.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        # Barre de statut
        self.var_statut = tk.StringVar(value="Prêt.")
        ttk.Label(main, textvariable=self.var_statut, foreground="#555555").grid(
            row=11, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

    # ------------------------------------------------------------------
    def _verifier_prerequis(self):
        if not TEMPLATE_FILE.exists():
            messagebox.showerror(
                "Fichier manquant",
                f"Le fichier '{TEMPLATE_FILE}' est introuvable dans :\n{SCRIPT_DIR}\n\n"
                "Place-le à côté de ce script avant de continuer.",
            )

    def _log(self, message: str):
        self.log_queue.put(message)

    def _traiter_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.txt_log.configure(state="normal")
                self.txt_log.insert("end", message + "\n")
                self.txt_log.see("end")
                self.txt_log.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._traiter_queue)

    def _ouvrir_dossier(self, dossier: Path):
        try:
            if sys.platform == "win32":
                os.startfile(dossier)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(dossier)])
            else:
                subprocess.run(["xdg-open", str(dossier)])
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le dossier :\n{exc}")

    # ------------------------------------------------------------------
    # Génération (lancée dans un thread pour ne pas geler l'interface)
    # ------------------------------------------------------------------
    def _lancer_generation(self):
        texte = self.var_texte.get().strip()
        if not texte:
            messagebox.showwarning("Champ manquant", "Merci de saisir un texte pour l'étiquette.")
            return
        if not TEMPLATE_FILE.exists():
            messagebox.showerror("Fichier manquant", f"'{TEMPLATE_FILE}' est introuvable.")
            return

        nom_sortie = self.var_nom.get().strip() or "etiquette"
        taille = self.var_taille.get()
        pictos = [
            "" if var.get() == PICTO_LABEL_AUCUN else var.get()
            for var in self.vars_pictos
        ]

        self.btn_generer.configure(state="disabled")
        self.var_statut.set("Génération en cours...")
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

        threading.Thread(
            target=self._generer_pdf,
            args=(taille, texte, pictos, nom_sortie),
            daemon=True,
        ).start()

    def _generer_pdf(self, taille, texte, pictos, nom_sortie):
        try:
            contenu = construire_contenu(taille, texte, pictos)

            # Le .tex final est écrit DIRECTEMENT dans export_latex/ :
            # jamais de fichier temporaire à la racine du dossier du script.
            tex_final = EXPORT_LATEX_DIR / f"{nom_sortie}.tex"
            tex_final.write_text(contenu, encoding="utf-8")
            self._log(f"Fichier .tex écrit : {tex_final}")

            self._log("Compilation avec pdflatex...")
            resultat = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    f"-output-directory={EXPORT_PDF_DIR}",
                    str(tex_final),
                ],
                capture_output=True, text=True,
            )

            # Nettoyage des fichiers auxiliaires, succès ou échec
            for ext in (".aux", ".log"):
                aux = EXPORT_PDF_DIR / f"{nom_sortie}{ext}"
                if aux.exists():
                    aux.unlink()

            if resultat.returncode != 0:
                self._log("Échec de la compilation. Dernières lignes du journal :")
                for ligne in resultat.stdout.splitlines()[-20:]:
                    self._log("  " + ligne)
                self.var_statut.set("Échec de la génération.")
                self.after(0, lambda: messagebox.showerror(
                    "Erreur de compilation",
                    "La compilation LaTeX a échoué. Consulte le journal pour le détail.",
                ))
                return

            pdf_dest = EXPORT_PDF_DIR / f"{nom_sortie}.pdf"
            self._log(f"PDF généré : {pdf_dest}")
            self.var_statut.set("Terminé avec succès.")
            self.after(0, lambda: messagebox.showinfo(
                "Succès", f"Étiquette générée avec succès :\n{pdf_dest}",
            ))

        except FileNotFoundError:
            self._log("Erreur : 'pdflatex' est introuvable dans le PATH.")
            self.var_statut.set("pdflatex introuvable.")
            self.after(0, lambda: messagebox.showerror(
                "pdflatex introuvable",
                "Installez une distribution LaTeX (TeX Live / MiKTeX) "
                "et vérifiez que 'pdflatex' est accessible dans le PATH.",
            ))
        except Exception as exc:
            self._log(f"Erreur inattendue : {exc}")
            self.var_statut.set("Erreur.")
            self.after(0, lambda: messagebox.showerror("Erreur", str(exc)))
        finally:
            self.after(0, lambda: self.btn_generer.configure(state="normal"))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
