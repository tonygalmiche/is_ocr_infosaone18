# -*- coding: utf-8 -*-
from odoo import fields, models  # type: ignore
from google import genai
from google.genai import types  # type: ignore
from PIL import Image
import base64


class IsOcrEmail(models.Model):
    _name = 'is.ocr.email'
    _inherit=['mail.thread']
    _description = "Mail pour intégration OCR"
    _order = 'id desc'
    _rec_name = 'mail_subject'


    mail_subject = fields.Char("Sujet", required=True, index=True, tracking=True)
    mail_from    = fields.Char("Expéditeur", tracking=True)
    mail_date    = fields.Datetime("Date", tracking=True)
    user_id      = fields.Many2one('res.users', "Utilisateur", tracking=True, readonly=True, help="Utilisateur associé à l'expéditeur du mail")
    ligne_ids    = fields.One2many('is.ocr.email.ligne', 'email_id', 'Pièces jointes à traiter')


class IsOcrEmailLigne(models.Model):
    _name = 'is.ocr.email.ligne'
    _inherit=['mail.thread']
    _description = "Pièces jointes des mails"
    _order='id'

    email_id     = fields.Many2one('is.ocr.email', 'Mail', required=True, ondelete='cascade')
    piece_jointe = fields.Char("Pièce jointe")
    image        = fields.Binary('Image')


    def action_open_form(self):
        """Ouvre la vue formulaire de la ligne"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pièce jointe',
            'res_model': 'is.ocr.email.ligne',
            'res_id': self.id,
            'view_mode': 'form',
            # 'target': 'new',
        }

    def action_download_image(self):
        """Télécharge l'image dans une application externe."""
        if self.image:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/image/{self._name}/{self.id}/image?download=true',
                'target': 'self',
            }
        else:
            raise Exception("Aucune image disponible à télécharger.")



    def analyse_gemini_action(self):
        company = self.env.company
        api_key = company.is_gemini_api_key
        client = genai.Client(api_key=api_key)
        if self.image:
            tmp_image_path = f"/tmp/{self.id}_image.jpeg"
            with open(tmp_image_path, "wb") as tmp_file:
                tmp_file.write(base64.b64decode(self.image))
            image_path = tmp_image_path
            
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

            print( response.text)



