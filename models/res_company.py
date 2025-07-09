# -*- coding: utf-8 -*-
from odoo import fields, models                       # type: ignore
from odoo.modules.module import get_module_path       # type: ignore
from odoo.exceptions import ValidationError,UserError # type: ignore
import os
from google import genai
from google.genai import types  # type: ignore
import base64
from PIL import Image
from io import BytesIO
import urllib.parse
import requests

import imaplib
from email import message_from_bytes
from email.header import decode_header
from urllib.parse import urlencode
from email.utils import parsedate_to_datetime
import datetime
import re


#TODO:
#- Traiter les images avec gemini
#- Créer le model pour récuprer les factures et les lignes 
#- Créer un compte avec le mail de l'expedutieur et afficher les facures unquement pour ce compte
#- Pour chaque facture pouvoir personnaliser le prompte pour améliorer le résultat
#- Convertir les PDF en images
#- Indiquer le temps de traitement de chaque facturre avec Gemini
#- Faire du ménage dans ce code


class ResCompany(models.Model):
    _inherit = 'res.company'

    is_gemini_api_key = fields.Char("Gemini API Key")
    is_gemini_model   = fields.Char("Modèle Gemini à utiliser", default="gemini-2.5-flash")
    is_gemini_prompt  = fields.Text("Prompt Gemini à utiliser")
    is_gemini_reponse = fields.Text("Réponse API Gemini", readonly=True)

    is_google_mail              = fields.Char("mail compte gMail")
    is_google_client_id         = fields.Char("Client id")
    is_google_client_secret     = fields.Char("Client secret")
    is_google_code_autorisation = fields.Char("Code d'autorisation")
    is_google_refresh_token     = fields.Char("refresh_token")
    is_google_reponse           = fields.Text("Réponse API gMail", readonly=True)



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


    def get_code_autorisation(self):
        CLIENT_ID = self.is_google_client_id # Client de bureau du projet
        # Construction de l'URL d'autorisation OAuth2 pour Gmail API
        redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        #scope = "https://mail.google.com/"
        SCOPE = [
            'https://mail.google.com/',
            'https://www.googleapis.com/auth/userinfo.email',
            'openid',
            'email'
        ]
        scope_str = " ".join(SCOPE)
        auth_url = (
            "https://accounts.google.com/o/oauth2/auth?"
            + urllib.parse.urlencode({
                "client_id": CLIENT_ID,
                "redirect_uri": redirect_uri,
                "scope": scope_str,
                "response_type": "code",
                "access_type": "offline",
                "prompt": "consent"
            })
        )
        msg="Ouvre cette URL dans ton navigateur pour obtenir le code d'autorisation :\n%s"%auth_url
        self.is_google_reponse = msg


    def get_refresh_token(self):
        CLIENT_ID = self.is_google_client_id
        CLIENT_SECRET = self.is_google_client_secret
        CODE_AUTORISATION = self.is_google_code_autorisation
        REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
        token_url = 'https://oauth2.googleapis.com/token'
        data = {
            'code': CODE_AUTORISATION,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        response = requests.post(token_url, data=data)
        tokens = response.json()
        refresh_token = tokens.get('refresh_token')
        if refresh_token:
            self.is_google_refresh_token = refresh_token
        else:
            raise ValidationError("Aucun refresh_token fourni. Il faut demander un nouveau code d'autorisation")


    def _get_access_token(self):
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            'client_id': self.is_google_client_id,
            'client_secret': self.is_google_client_secret,
            'refresh_token': self.is_google_refresh_token,
            'grant_type': 'refresh_token',
        }
        r = requests.post(token_url, data=data)
        if r.ok:
            access_token = r.json()['access_token']
            return access_token
        else:
            msg = "Erreur lors du rafraîchissement du token:\n%s"%r.text
            raise ValidationError(msg)


    def get_access_token(self):
        res = self._get_access_token()
        self.is_google_reponse = res
      

    def _get_email_address(self):
        access_token =  self._get_access_token()
        r = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        if r.ok:
            email_address =  r.json()['email']
            return email_address
        else:
            msg = "Erreur lors de la récupération de l'adresse email:\n%s"%r.text
            raise ValidationError(msg)


    def get_email_address(self):
        email_address = self._get_email_address()
        self.is_google_reponse = email_address


    def _get_authenticate_imap(self):
        "Connexion IMAP avec XOAUTH2"
        access_token = self._get_access_token()
        email_address = self._get_email_address()
        auth_string = f"user={email_address}\x01auth=Bearer {access_token}\x01\x01"
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        imap.authenticate('XOAUTH2', lambda x: auth_string.encode())
        return imap


    def get_mails(self):
        imap = self._get_authenticate_imap()

        #** Lister les nouveaux mails non lus *********************************
        imap.select("INBOX")
        typ, data = imap.search(None, 'UNSEEN')
        if typ != 'OK':
            print("Erreur lors de la recherche des mails.")
            return
        mail_ids = data[0].split()
        reponses=[]
        txt = f"{len(mail_ids)} nouveaux mails non lus."
        reponses.append(txt)
        for num in mail_ids:
            typ, msg_data = imap.fetch(num, '(RFC822)')
            if typ != 'OK':
                print("Erreur lors de la récupération du mail.")
                continue
            msg = message_from_bytes(msg_data[0][1])
            raw_subject = msg["Subject"]
            if raw_subject is not None:
                subject, encoding = decode_header(raw_subject)[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors='replace')
            else:
                subject = "(sans sujet)"
            txt = f"De: {msg['From']}\nSujet: {subject}\nDate: {msg['Date']}\n---"
            reponses.append(txt)
        self.is_google_reponse = '\n'.join(reponses)
        #**********************************************************************
        imap.logout()


    def get_pieces_jointes_mails(self):
        """
        Extrait les pièces jointes (photos et PDF) des emails non lus et les enregistre dans le dossier 'factures'
        """
        print(self)
        folder='INBOX'
        max_emails=3

        print(f"\n=== Extraction des pièces jointes des emails non lus de {folder} ===")
        
        # Créer le dossier 'factures' s'il n'existe pas
        factures_dir = '/tmp/factures'
        if not os.path.exists(factures_dir):
            os.makedirs(factures_dir)
            print(f"📁 Dossier '{factures_dir}' créé.")
    
        # Sélectionner le dossier
        imap = self._get_authenticate_imap()
        status, messages = imap.select(folder)
        if status != 'OK':
            print(f"❌ Erreur lors de la sélection du dossier {folder}: {messages}")
            return
        
        # Rechercher uniquement les emails non lus
        status, messages = imap.search(None, 'UNSEEN')
        if status != 'OK':
            print("❌ Erreur lors de la recherche des emails non lus")
            return
        
        email_ids = messages[0].split()
        unread_count = len(email_ids)
        
        print(f"📧 {unread_count} emails non lus trouvés")
        if unread_count == 0:
            print("📭 Aucun email non lu à traiter")
            return
        attachment_count = 0        
        ct=0
        for email_id in email_ids:
            ct+=1
            if ct>max_emails:
                return
            # Récupérer l'email complet
            status, msg_data = imap.fetch(email_id, '(RFC822)')
            if status != 'OK':
                continue
            
            # Parser l'email
            email_message = message_from_bytes(msg_data[0][1])
            
            # Informations de l'email
            subject = email_message.get('Subject', 'Sans sujet')
            sender = email_message.get('From', 'Expéditeur inconnu')
            date_str = email_message.get('Date', 'Date inconnue')

            print('👤',ct,subject,sender,date_str)

            try:
                # Parser la date de l'email
                email_date = parsedate_to_datetime(date_str)
                # Formater la date pour le nom de fichier (YYYY-MM-DD_HH-MM-SS)
                date_prefix = email_date.strftime('%Y-%m-%d_%H-%M-%S')
            except Exception:
                # Si parsing échoue, utiliser timestamp actuel
                date_prefix = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            
            # Extraire l'email de l'expéditeur (nettoyer le nom d'affichage)
            sender_email = sender
            # Extraire l'email entre < > si présent
            email_match = re.search(r'<([^>]+)>', sender)
            if email_match:
                sender_email = email_match.group(1)
            else:
                # Si pas de < >, prendre directement le sender s'il ressemble à un email
                if '@' in sender:
                    sender_email = sender.split()[0] if ' ' in sender else sender
            
            # Nettoyer le nom d'email pour créer un nom de dossier valide
            safe_sender = re.sub(r'[<>:"/\\|?*]', '_', sender_email)
            safe_sender = safe_sender.replace(' ', '_')
            
            # Créer le sous-dossier pour cet expéditeur
            sender_dir = os.path.join(factures_dir, safe_sender)
            if not os.path.exists(sender_dir):
                os.makedirs(sender_dir)
                print(f"📁 Sous-dossier créé: {safe_sender}")
            
            # Parcourir les parties de l'email
            for part in email_message.walk():
                # Vérifier si c'est une pièce jointe
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()
                    if filename:
                        # Filtrer les types de fichiers (images et PDF)
                        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
                        if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'pdf']:
                            try:
                                # Récupérer le contenu de la pièce jointe
                                content = part.get_payload(decode=True)
                                # Créer un nom de fichier avec date et heure de réception
                                safe_filename = f"{date_prefix}_{email_id.decode()}_{filename}"
                                file_path = os.path.join(sender_dir, safe_filename)
                                # Enregistrer le fichier dans le sous-dossier de l'expéditeur
                                with open(file_path, 'wb') as f:
                                    f.write(content)
                                attachment_count += 1
                                file_size = len(content) / 1024  # Taille en KB
                                print(f"- ✅ Pièce jointe sauvegardée: {safe_sender}/{safe_filename} ({file_size:.1f} KB)")  
                            except Exception as e:
                                print(f"❌ Erreur lors de la sauvegarde de {filename}: {e}")


          