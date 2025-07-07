# -*- coding: utf-8 -*-
from odoo import fields, models # type: ignore
from odoo.modules.module import get_module_path
import os
from google import genai
from google.genai import types
import base64
from PIL import Image
from io import BytesIO


class ResCompany(models.Model):
    _inherit = 'res.company'

    is_gemini_api_key = fields.Char("Gemini API Key")
    is_gemini_model   = fields.Char("Modèle Gemini à utiliser", default="gemini-2.5-flash")
    is_gemini_prompt  = fields.Text("Prompt Gemini à utiliser")
    is_gemini_reponse = fields.Text("Réponse API Gemini", readonly=True)


    def test_connexion_api(self):
        company = self.env.company
        api_key = company.is_gemini_api_key
        try:
            client = genai.Client(api_key=api_key)
            # On tente une requête simple pour vérifier la validité de la clé
            # Ici, on tente de récupérer le nom du modèle par défaut pour tester la clé
            response = client.models.list()
            reponse=[]
            for model in response:
                reponse.append(model.name)
            reponse = '\n'.join(reponse)
            self.is_gemini_reponse = reponse
            if not response:
                raise Exception("Aucune réponse du modèle, clé peut-être invalide")
        except Exception as e:
            message = f"Problème de connexion: {e}"
            notif_type = 'danger'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Test de connexion Gemini',
                    'message': message,
                    'sticky': False,
                    'type': notif_type,
                }
            }


    def get_info_ticket(self):
        company = self.env.company
        api_key = company.is_gemini_api_key
        client = genai.Client(api_key=api_key)
        module_path = get_module_path('is_ocr_infosaone18')
        image_path = f"{module_path}/ticket_caisse/brico_depot.jpeg"
        image = Image.open(image_path)
        if company.is_gemini_prompt:
            prompt = company.is_gemini_prompt
        else:
            prompt = """
                Voici un ticket de caisse (Français ou Italien). Peux-tu extraire les champs suivants :
                - ville : ville
                - adresse_complete : Adresse complète avec la rue, le CP et la ville
                - date_facture : Date du ticket au format JJ/MM/AAAA
                - nom_fournisseur : Nom du fournisseur
                - montant_ht : Montant HT au format numérique avec 2 décimales
                - taux_tva : Taux de TVA au format numérique avec 2 décimales
                - montant_tva : Montant TVA (ou DI CUI IVA) au format numérique avec 2 décimales
                - montant_ttc : Montant TTC (ou TOTALE COMPLESSIVO) au format numérique avec 2 décimales
                - eco_contribution : Montant Eco contribution  au format numérique avec 2 décimales

                Sur la ligne "Total TVA", tu peux trouver dans cet ordre : montant_ht, montant_tva et montant_ttc
                Si tu vois plusieurs taux de tva, donne moi le détail (detail_tva):
                - taux_tva
                - montant_tva

                Donne moi le détail des lignes (detail_lignes):
                - article : Désignation de l'article
                - taux_tva : Taux de TVA (ou IVA)
                - montant : Montant

                Calul le total des montant des lignes (total_montant) et l'écart (ecart) entre total_montant et montant_ttc


                Ne fait aucun calcul, si tu ne trouves pas un montant, tu met none à la place

                Retourne la réponse au format JSON.
            """

        # https://ai.google.dev/gemini-api/docs/models?hl=fr
        # models/gemini-2.5-flash  =>  Gemini 2.5 Flash => Plus rapide mais moins précis
        # models/gemini-2.5-pro    =>  Gemini 2.5 Pro   => Plus lent, plus chère mais plus précis
        if company.is_gemini_model:
            model = company.is_gemini_model
        else:
            model = "gemini-2.5-flash"
        response = client.models.generate_content(
            model=model,
            contents=[
                {"text": prompt},
                image
            ],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"]  # On demande uniquement du texte en retour
            )
        )
        self.is_gemini_reponse = response.text