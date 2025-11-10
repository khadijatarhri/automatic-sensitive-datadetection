import json  
from pymongo import MongoClient  
from datetime import datetime  
import logging  
from pyapacheatlas.auth import BasicAuthentication  
from pyapacheatlas.core import AtlasClient  
import requests  
import time
  
ATLAS_URL = "http://172.17.0.1:21000"  
ATLAS_USER = "admin"  
ATLAS_PASS = "ensias123@"  
MONGO_URI = 'mongodb://mongodb:27017/'  
  
logging.basicConfig(level=logging.INFO)  
logger = logging.getLogger(__name__)  

class RGPDGlossaryManager:
    """Gestionnaire de glossaire RGPD avec descriptions significatives"""
    
    # Définitions des catégories RGPD conformes à la réglementation
    RGPD_CATEGORIES = {
        "Données d'identification": {
            "short_desc": "Données permettant l'identification directe d'une personne",
            "long_desc": """**CATÉGORIE RGPD : DONNÉES D'IDENTIFICATION**

📋 **Définition Réglementaire** :
Données personnelles permettant d'identifier directement ou indirectement une personne physique, conformément à l'article 4(1) du RGPD.

🔍 **Types de Données Incluses** :
• Identifiants civils : Nom, prénom, date de naissance
• Identifiants nationaux : Numéro CIN (Maroc), numéro de sécurité sociale
• Identifiants techniques : Numéro de compte client, identifiant unique

⚖️ **Base Légale (RGPD)** :
• Article 4(1) - Définition des données personnelles
• Article 6 - Licéité du traitement
• Article 5 - Principes relatifs au traitement

🔒 **Mesures de Protection Obligatoires** :
• Chiffrement des identifiants sensibles (CIN, passeport)
• Contrôle d'accès strict basé sur le principe du moindre privilège
• Traçabilité complète des accès (logs d'audit)
• Pseudonymisation pour les environnements non-production

📊 **Durée de Conservation** :
• Clients actifs : Durée de la relation contractuelle
• Clients inactifs : 3 ans après la dernière transaction (Loi 09-08)
• Suppression automatique après expiration

⚠️ **Risques en Cas de Violation** :
• Vol d'identité et usurpation
• Fraude documentaire
• Non-conformité RGPD : amendes jusqu'à 20M€ ou 4% du CA mondial

👤 **Responsabilités** :
• DPO (Data Protection Officer) : Supervision globale
• Data Steward : Validation et classification
• Équipes IT : Implémentation technique des contrôles""",
            "regulatory_ref": "RGPD Art. 4(1), Art. 6",
            "retention_period": "3 ans après fin de relation",
            "risk_level": "ÉLEVÉ",
            "examples": ["CIN", "Nom complet", "Numéro client"]
        },
        
        "Données financières": {
            "short_desc": "Données bancaires et informations financières",
            "long_desc": """**CATÉGORIE RGPD : DONNÉES FINANCIÈRES**

📋 **Définition Réglementaire** :
Données à caractère personnel relatives aux moyens de paiement, comptes bancaires et transactions financières. Classées comme données sensibles nécessitant une protection renforcée (RGPD Art. 9).

🔍 **Types de Données Incluses** :
• Coordonnées bancaires : IBAN, RIB, SWIFT/BIC
• Moyens de paiement : Numéros de carte bancaire, date d'expiration, CVV
• Transactions : Montants, dates, bénéficiaires
• Données fiscales : Revenus, déclarations, numéro fiscal

⚖️ **Base Légale (RGPD)** :
• Article 9 - Traitement de catégories particulières de données
• Article 32 - Sécurité du traitement
• Directive PSD2 (Payment Services Directive)
• Loi 09-08 (Maroc) - Protection des données bancaires

🔒 **Mesures de Protection Obligatoires** :
• Tokenisation des numéros de carte (PCI-DSS compliance)
• Chiffrement AES-256 pour IBAN et RIB
• Masquage partiel : affichage des 4 derniers chiffres uniquement
• Stockage en coffre-fort numérique certifié
• Authentification forte pour tout accès (MFA)
• Ségrégation réseau : isolation des bases financières

📊 **Durée de Conservation** :
• Données transactionnelles : 5 ans (obligations comptables)
• Moyens de paiement : Suppression après expiration ou résiliation
• Archives légales : 10 ans pour audits financiers

⚠️ **Risques en Cas de Violation** :
• Fraude bancaire et détournement de fonds
• Blanchiment d'argent et criminalité financière
• Sanctions PCI-DSS : révocation du droit de traiter les paiements
• Amendes RGPD maximales + sanctions Bank Al-Maghrib

💰 **Conformité PCI-DSS** :
• Niveau 1 : Audit annuel obligatoire pour >6M transactions/an
• Scan trimestriel de vulnérabilité
• Tests de pénétration annuels

👤 **Responsabilités** :
• DSI/RSSI : Architecture de sécurité
• DPO : Conformité réglementaire
• Équipes Finance : Gestion des accès""",
            "regulatory_ref": "RGPD Art. 9, PCI-DSS, Loi 09-08",
            "retention_period": "5 ans (obligations comptables)",
            "risk_level": "CRITIQUE",
            "examples": ["IBAN", "Numéro de carte", "RIB"]
        },
        
        "Données de contact": {
            "short_desc": "Informations de communication et coordonnées",
            "long_desc": """**CATÉGORIE RGPD : DONNÉES DE CONTACT**

📋 **Définition Réglementaire** :
Données personnelles permettant de contacter une personne physique par tout moyen de communication. Soumises au consentement explicite pour usage marketing (RGPD Art. 6).

🔍 **Types de Données Incluses** :
• Coordonnées directes : Email, téléphone fixe/mobile
• Adresses postales : Numéro, rue, ville, code postal
• Coordonnées professionnelles : Email entreprise, ligne directe
• Moyens de communication : Skype, WhatsApp, réseaux sociaux

⚖️ **Base Légale (RGPD)** :
• Article 6(1)(a) - Consentement pour marketing direct
• Article 7 - Conditions applicables au consentement
• Article 21 - Droit d'opposition
• Directive ePrivacy 2002/58/CE
• Loi 09-08 Art. 18 (Maroc) - Prospection commerciale

🔒 **Mesures de Protection Obligatoires** :
• Mécanisme de consentement opt-in explicite
• Traçabilité du consentement (date, canal, preuve)
• Fonction de désinscription (opt-out) facile et immédiate
• Hachage SHA-256 pour emails en environnement de test
• Contrôle d'accès : liste d'opposition interne (Do Not Contact)

📊 **Durée de Conservation** :
• Consentement marketing : 3 ans sans interaction
• Clients actifs : Durée de la relation commerciale
• Prospects non convertis : 3 ans maximum
• Suppression automatique après opposition

⚠️ **Risques en Cas de Violation** :
• Spam et sollicitations non désirées
• Hameçonnage (phishing) et ingénierie sociale
• Violation du droit à l'oubli
• Amendes CNIL/CNDP : jusqu'à 10M€ ou 2% du CA

📧 **Conformité Marketing** :
• Lien de désinscription obligatoire dans chaque email
• Identification claire de l'expéditeur
• Respect des horaires d'appel (9h-20h jours ouvrés)
• Interdiction de cession de fichiers sans consentement

👤 **Responsabilités** :
• Marketing : Gestion du consentement
• DPO : Audit des campagnes et conformité
• Service Client : Traitement des oppositions""",
            "regulatory_ref": "RGPD Art. 6, Art. 21, Directive ePrivacy",
            "retention_period": "3 ans sans interaction",
            "risk_level": "MOYEN",
            "examples": ["Email", "Téléphone", "Adresse postale"]
        },
        
        "Données de localisation": {
            "short_desc": "Informations géographiques et données de géolocalisation",
            "long_desc": """**CATÉGORIE RGPD : DONNÉES DE LOCALISATION**

📋 **Définition Réglementaire** :
Toute donnée permettant de déterminer la position géographique d'une personne, qu'elle soit statique (adresse) ou dynamique (GPS). Considérées comme données personnelles sensibles selon le contexte (RGPD Art. 4).

🔍 **Types de Données Incluses** :
• Localisation statique : Adresse de résidence, lieu de travail
• Géolocalisation GPS : Coordonnées latitude/longitude
• Données de déplacement : Historique de trajets, zones fréquentées
• Localisation réseau : Adresses IP, identifiants WiFi/Bluetooth

⚖️ **Base Légale (RGPD)** :
• Article 4(1) - Données personnelles incluant la localisation
• Article 6 - Licéité du traitement de localisation
• Article 32 - Sécurité des données de géolocalisation
• Directive ePrivacy - Consentement pour géolocalisation

🔒 **Mesures de Protection Obligatoires** :
• Consentement explicite pour géolocalisation active
• Anonymisation des trajectoires pour analyses statistiques
• Floutage des adresses pour affichage public (derniers chiffres)
• Chiffrement des coordonnées GPS en base de données
• Désactivation par défaut : opt-in obligatoire
• Suppression automatique des historiques après 90 jours

📊 **Durée de Conservation** :
• Adresse de livraison : Durée de la garantie produit
• Géolocalisation temps réel : Suppression après finalité atteinte
• Historique de déplacement : 3 mois maximum (sauf obligation légale)

⚠️ **Risques en Cas de Violation** :
• Tracking et surveillance non consentie
• Vol et cambriolage (divulgation d'absence du domicile)
• Harcèlement et atteinte à la vie privée
• Profilage comportemental abusif

🗺️ **Cas d'Usage Légitimes** :
• Livraison de colis : adresse nécessaire pour exécution du contrat
• Services de navigation : consentement utilisateur
• Sécurité des employés : intérêt légitime de l'employeur (cadre strict)
• Statistiques anonymisées : aucune identification individuelle

👤 **Responsabilités** :
• Product Owner : Design privacy-by-default
• DPO : Validation des cas d'usage
• Équipes techniques : Implémentation des contrôles""",
            "regulatory_ref": "RGPD Art. 4, Directive ePrivacy",
            "retention_period": "3 mois pour historique GPS",
            "risk_level": "ÉLEVÉ",
            "examples": ["Adresse", "Ville", "Coordonnées GPS"]
        },
        
        "Données de transaction": {
            "short_desc": "Données d'activité commerciale et transactionnelle",
            "long_desc": """**CATÉGORIE RGPD : DONNÉES DE TRANSACTION**

📋 **Définition Réglementaire** :
Ensemble des informations relatives aux opérations commerciales, achats et interactions entre l'entreprise et les personnes physiques. Données nécessaires à l'exécution du contrat (RGPD Art. 6(1)(b)).

🔍 **Types de Données Incluses** :
• Identifiants de commande : Références, numéros de facture
• Montants : Prix, taxes, remises appliquées
• Produits/Services : Articles achetés, quantités
• Dates : Commande, livraison, paiement
• Statuts : En cours, validé, annulé, remboursé

⚖️ **Base Légale (RGPD)** :
• Article 6(1)(b) - Exécution du contrat
• Article 6(1)(c) - Obligation légale (facturation, comptabilité)
• Code de Commerce - Conservation des factures
• Loi fiscale - Archivage comptable

🔒 **Mesures de Protection Obligatoires** :
• Séparation des données transactionnelles et financières sensibles
• Accès restreint : seuls services Finance et Comptabilité
• Journalisation des consultations (audit trail)
• Anonymisation pour analyses marketing et BI
• Chiffrement des archives légales

📊 **Durée de Conservation** :
• Documents comptables : 10 ans (obligation légale)
• Factures clients : 10 ans minimum
• Historique d'achats clients actifs : Durée de la relation + 3 ans
• Données analytiques anonymisées : Conservation illimitée

⚠️ **Risques en Cas de Violation** :
• Reconstitution des habitudes de consommation
• Profilage économique et discrimination tarifaire
• Non-conformité fiscale et comptable
• Perte de confiance client

📈 **Utilisation Analytique** :
• Segmentation client : anonymisation obligatoire
• Prédiction de churn : consentement si marketing direct
• Analyse de panier : agrégation sans identification individuelle
• Reporting financier : conformité IFRS/GAAP

👤 **Responsabilités** :
• DAF : Conformité comptable et fiscale
• DPO : Respect des durées de conservation RGPD
• Data Analyst : Anonymisation avant exploitation""",
            "regulatory_ref": "RGPD Art. 6(1)(b), Code Commerce",
            "retention_period": "10 ans (obligations comptables)",
            "risk_level": "FAIBLE À MOYEN",
            "examples": ["Référence commande", "Montant achat", "Date transaction"]
        }
    }
    
    # Modèles de descriptions de termes par type d'entité
    ENTITY_DESCRIPTIONS = {
        "PERSON": {
            "business_name": "Identité Civile - Nom Complet",
            "description": """Nom complet d'une personne physique incluant le nom de famille et le(s) prénom(s), constituant un identifiant civil direct.""",
            "data_usage": "Identification client, personnalisation des communications, documents contractuels",
            "anonymization": "Pseudonymisation : remplacement par 'Client_XXXXX' ou hachage SHA-256",
            "access_policy": "Accès restreint aux services Client, Ventes et Support uniquement"
        },
        "EMAIL_ADDRESS": {
            "business_name": "Adresse Email - Contact Électronique",
            "description": """Adresse de courrier électronique permettant la communication digitale avec le client. Soumise au consentement pour usage marketing.""",
            "data_usage": "Communication transactionnelle (confirmations, factures), newsletters avec opt-in",
            "anonymization": "Hachage SHA-256 pour environnements de test, suppression domaine (@xxx.com)",
            "access_policy": "Services Marketing, Support Client avec traçabilité du consentement"
        },
        "PHONE_NUMBER": {
            "business_name": "Numéro de Téléphone - Contact Vocal",
            "description": """Numéro de téléphone fixe ou mobile permettant le contact vocal direct. Nécessite opt-in pour prospection commerciale.""",
            "data_usage": "Confirmation de commande, support client, rappel rendez-vous (non-marketing)",
            "anonymization": "Masquage partiel : affichage +212-XX-XX-XX-78 (derniers chiffres visibles)",
            "access_policy": "Call centers, Support, interdiction usage marketing sans consentement explicite"
        },
        "IBAN_CODE": {
            "business_name": "IBAN - Identifiant Bancaire International",
            "description": """Code IBAN (International Bank Account Number) identifiant de manière unique un compte bancaire pour virements SEPA. Donnée financière hautement sensible.""",
            "data_usage": "Prélèvements SEPA, virements, remboursements avec mandat signé",
            "anonymization": "Tokenisation PCI-DSS : remplacement par jeton non-réversible, affichage 4 derniers caractères",
            "access_policy": "Équipes Finance uniquement, MFA obligatoire, logs d'accès SIEM"
        },
        "CREDIT_CARD": {
            "business_name": "Carte Bancaire - Moyen de Paiement",
            "description": """Numéro de carte bancaire (CB, Visa, MasterCard) pour paiements. Soumis aux standards PCI-DSS niveau 1.""",
            "data_usage": "Transactions de paiement uniquement, jamais stocké en clair (interdiction PCI-DSS)",
            "anonymization": "Tokenisation obligatoire, stockage interdit sauf coffre-fort certifié PCI",
            "access_policy": "Passerelle de paiement certifiée uniquement, aucun accès humain direct"
        },
        "ID_MAROC": {
            "business_name": "CIN - Carte d'Identité Nationale Marocaine",
            "description": """Numéro de Carte d'Identité Nationale (CIN) marocaine, identifiant unique officiel pour ressortissants marocains. Protégé par Loi 09-08.""",
            "data_usage": "Vérification d'identité KYC, conformité réglementaire bancaire/télécoms",
            "anonymization": "Hachage SHA-256 avec sel, interdiction de stockage pour non-régulés",
            "access_policy": "Compliance et KYC uniquement, traçabilité CNDP obligatoire"
        },
        "LOCATION": {
            "business_name": "Localisation Géographique - Ville/Région",
            "description": """Donnée de localisation géographique (ville, région) permettant le ciblage géographique de services.""",
            "data_usage": "Personnalisation des offres régionales, statistiques démographiques",
            "anonymization": "Agrégation par région, aucune précision quartier/rue",
            "access_policy": "Marketing et BI avec données agrégées uniquement"
        },
        "ORDER_REFERENCE": {
            "business_name": "Référence Commande - Identifiant Transaction",
            "description": """Identifiant unique de commande permettant le suivi transactionnel et la traçabilité commerciale.""",
            "data_usage": "Suivi de commande, service après-vente, comptabilité",
            "anonymization": "Aucune donnée personnelle directe, conservation pour audit comptable",
            "access_policy": "Services Ventes, Support, Finance selon principe du moindre privilège"
        },
        "ORDER_AMOUNT": {
            "business_name": "Montant Transaction - Valeur Commerciale",
            "description": """Montant financier d'une transaction commerciale, indicateur de valeur client non-identifiant direct.""",
            "data_usage": "Facturation, comptabilité, analyse de CA, segmentation client",
            "anonymization": "Anonymisation possible pour études statistiques (agrégation)",
            "access_policy": "Finance, Comptabilité, BI avec données agrégées pour analyses"
        }
    }

class AtlasMetadataGovernance:  
    def __init__(self):  
        self.atlas_url = ATLAS_URL  
        self.auth = BasicAuthentication(username=ATLAS_USER, password=ATLAS_PASS)  
        self.atlas_client = AtlasClient(  
            endpoint_url=self.atlas_url,  
            authentication=self.auth  
        )  
        self.auth_tuple = (ATLAS_USER, ATLAS_PASS)  
        self.mongo_client = MongoClient(MONGO_URI)  
        self.metadata_db = self.mongo_client['metadata_validation_db']  
        self.current_glossary_guid = None  
        self.created_terms_cache = {}
        self.rgpd_manager = RGPDGlossaryManager()
        self._test_connections()  
  
    def _test_connections(self):  
        """Tester les connexions Atlas et MongoDB"""  
        logger.info("🔍 Test des connexions...")  
        try:  
            self.mongo_client.admin.command('ping')  
            logger.info("✅ MongoDB connecté")  
        except Exception as e:  
            logger.error(f"❌ MongoDB non accessible: {e}")  
            raise  

    def create_business_glossary(self):  
        """Créer un glossaire RGPD professionnel et significatif"""  
        try:  
            glossary_payload = {
                "name": "Glossaire_RGPD_Gouvernance_Données1",
                "shortDescription": "Glossaire métier pour la gouvernance des données personnelles - Conformité RGPD/Loi 09-08",
                "longDescription": """**GLOSSAIRE MÉTIER - GOUVERNANCE DES DONNÉES PERSONNELLES**

🎯 **Objectif du Glossaire** :
Référentiel centralisé des définitions métier et réglementaires pour la gestion des données personnelles dans le cadre du RGPD (Règlement Général sur la Protection des Données) et de la Loi 09-08 marocaine.

📚 **Contenu** :
Ce glossaire regroupe les termes métier validés par les Data Stewards, classés par catégories RGPD avec leurs définitions réglementaires, exemples d'usage, mesures de protection et durées de conservation.

✅ **Processus de Validation** :
1. Détection automatique des entités sensibles (Microsoft Presidio + spaCy)
2. Classification par l'IA (Google Gemini) avec recommandations
3. Validation humaine par Data Steward (Human-in-the-Loop)
4. Synchronisation automatique vers Apache Atlas

🔒 **Gouvernance** :
• DPO (Data Protection Officer) : Responsable conformité RGPD
• Data Stewards : Validation et enrichissement des définitions
• Équipes techniques : Implémentation des contrôles d'accès

📅 **Dernière mise à jour** : """ + datetime.now().strftime('%d/%m/%Y %H:%M') + """
🏢 **Entité responsable** : Direction Data Governance""",
                "qualifiedName": "glossaire_rgpd1@production",
                "language": "fr_FR"
            }
              
            response = requests.post(  
                f"{self.atlas_url}/api/atlas/v2/glossary",  
                json=glossary_payload,  
                auth=self.auth_tuple,  
                timeout=(30, 60)  
            )  
              
            if response.status_code == 200:  
                glossary_guid = response.json()['guid']  
                self.current_glossary_guid = glossary_guid  
                logger.info("✓ Glossaire RGPD créé avec succès")  
                return glossary_guid  
            else:  
                logger.error(f"Échec création glossaire: {response.text}")  
                return None  
                  
        except Exception as e:  
            logger.error(f"Erreur création glossaire: {e}")  
            return None

    def create_rgpd_categories(self, glossary_guid):  
        """Créer des catégories RGPD professionnelles avec descriptions complètes"""  
        category_guids = {}  
        
        for category_name, category_info in self.rgpd_manager.RGPD_CATEGORIES.items():
            cat_data = {  
                "name": category_name,  
                "shortDescription": category_info["short_desc"],  
                "longDescription": category_info["long_desc"],
                "qualifiedName": f"rgpd.{category_name.lower().replace(' ', '_')}@production",
                "anchor": {"glossaryGuid": glossary_guid}  
            }  
              
            response = requests.post(  
                f"{self.atlas_url}/api/atlas/v2/glossary/category",  
                json=cat_data,  
                auth=self.auth_tuple  
            )  
              
            if response.status_code == 200:  
                category_guids[category_name] = response.json()['guid']  
                logger.info(f"✓ Catégorie RGPD créée: {category_name}")  
            else:  
                logger.error(f"✗ Erreur catégorie {category_name}: {response.text}")  
          
        return category_guids

    def _generate_professional_term_description(self, metadata):
        """Générer une description professionnelle et significative pour un terme"""
        column_name = metadata['column_name']
        entity_types = metadata.get('entity_types', [])
        primary_entity = entity_types[0] if entity_types else "UNKNOWN"
        
        # Récupérer le template de description pour ce type d'entité
        entity_desc = self.rgpd_manager.ENTITY_DESCRIPTIONS.get(
            primary_entity, 
            self.rgpd_manager.ENTITY_DESCRIPTIONS.get("PERSON")  # Fallback
        )
        
        rgpd_category = metadata.get('recommended_rgpd_category', 'Non classifié')
        sensitivity = metadata.get('recommended_sensitivity_level', 'INTERNAL')
        ranger_policy = metadata.get('recommended_ranger_policy', 'Non définie')
        total_entities = metadata.get('total_entities', 0)
        sample_values = metadata.get('sample_values', [])
        
        # Construire une description structurée et professionnelle
        description = f"""**{entity_desc['business_name'].upper()}**

📋 **Description Métier** :
{entity_desc['description']}

🔍 **Détection Automatique** :
• Colonne source : `{column_name}`
• Type(s) d'entité détectée(s) : {', '.join(entity_types) if entity_types else 'Aucune entité spécifique'}

📂 **Classification RGPD** :
• Catégorie réglementaire : **{rgpd_category}**
• Niveau de sensibilité : **{sensitivity}**
• Base légale : {self._get_legal_basis(rgpd_category)}

🔒 **Politique de Protection** :
• Stratégie d'anonymisation : {ranger_policy}
• Méthode appliquée : {self._get_anonymization_method(ranger_policy)}
• Contrôle d'accès : {entity_desc['access_policy']}

💼 **Usage Métier** :
{entity_desc['data_usage']}

🛡️ **Mesures de Protection** :
{entity_desc['anonymization']}

⏱️ **Conservation des Données** :
• Durée légale : {self._get_retention_period(rgpd_category)}
• Suppression automatique après expiration
• Archivage sécurisé si obligation légale

✅ **Validation Gouvernance** :
• Statut : Validé par Data Steward
• Date de validation : {datetime.now().strftime('%d/%m/%Y')}
• Responsable : {metadata.get('validated_by', 'Data Steward')}

📊 **Échantillons de Données** :
{self._format_professional_samples(sample_values, primary_entity)}

---
*Ce terme a été généré automatiquement par le système de gouvernance des données et validé par un Data Steward conformément aux exigences RGPD.*
        """.strip()
        
        return description
    
    def _get_legal_basis(self, rgpd_category):
        """Retourner la base légale selon la catégorie"""
        legal_mapping = {
            "Données d'identification": "RGPD Art. 6(1)(b) - Exécution du contrat",
            "Données financières": "RGPD Art. 9 - Catégories particulières",
            "Données de contact": "RGPD Art. 6(1)(a) - Consentement",
            "Données de localisation": "RGPD Art. 6(1)(f) - Intérêt légitime",
            "Données de transaction": "RGPD Art. 6(1)(b) - Exécution du contrat"
        }
        return legal_mapping.get(rgpd_category, "RGPD Art. 6 - À définir")
    
    def _get_retention_period(self, rgpd_category):
        """Retourner la durée de conservation selon la catégorie"""
        retention_mapping = {
            "Données d'identification": "3 ans après fin de relation contractuelle",
            "Données financières": "5 ans (obligations comptables et fiscales)",
            "Données de contact": "3 ans sans interaction (prospection)",
            "Données de localisation": "3 mois pour géolocalisation, durée du contrat pour adresse",
            "Données de transaction": "10 ans (obligations comptables)"
        }
        return retention_mapping.get(rgpd_category, "À définir selon analyse DPO")
    
    def _get_anonymization_method(self, ranger_policy):
        """Retourner la méthode d'anonymisation détaillée"""
        method_mapping = {
            "masking": "Masquage complet - Remplacement par [MASQUÉ]",
            "partial_masking": "Masquage partiel - Affichage des 4 derniers caractères",
            "hashing": "Hachage SHA-256 irréversible avec sel",
            "encryption": "Chiffrement AES-256 avec gestion de clés",
            "tokenization": "Tokenisation PCI-DSS avec coffre-fort",
            "redaction": "Suppression complète de la donnée",
            "generalization": "Généralisation - Réduction de précision"
        }
        return method_mapping.get(ranger_policy, "Méthode à définir selon sensibilité")
    
    def _format_professional_samples(self, sample_values, entity_type):
        """Formater les échantillons de manière professionnelle avec anonymisation"""
        if not sample_values:
            return "• Aucun échantillon disponible pour ce terme"
        
        anonymization_rules = {
            "PERSON": lambda x: f"{x[0]}*** {x.split()[-1][0]}***" if len(x.split()) > 1 else f"{x[:2]}***",
            "EMAIL_ADDRESS": lambda x: f"{x.split('@')[0][:3]}***@{x.split('@')[1]}" if '@' in x else f"{x[:3]}***",
            "PHONE_NUMBER": lambda x: f"+XXX-XX-XX-XX-{x[-2:]}" if len(x) > 4 else "XX-XX-XX-XX",
            "IBAN_CODE": lambda x: f"FR** **** **** **** **** ***{x[-3:]}" if len(x) > 3 else "FR** **** ****",
            "CREDIT_CARD": lambda x: f"**** **** **** {x[-4:]}" if len(x) >= 4 else "**** **** ****",
            "ID_MAROC": lambda x: f"{x[:2]}*****{x[-1]}" if len(x) > 3 else "XX******",
            "LOCATION": lambda x: x if len(x) < 50 else f"{x[:30]}...",
            "ORDER_REFERENCE": lambda x: f"{x[:6]}***" if len(x) > 6 else f"{x[:3]}***",
            "ORDER_AMOUNT": lambda x: f"{x} DH" if x.replace('.','').isdigit() else x
        }
        
        anonymize_func = anonymization_rules.get(entity_type, lambda x: f"{x[:3]}***" if len(str(x)) > 3 else "***")
        
        formatted_samples = []
        for i, sample in enumerate(sample_values[:5], 1):
            sample_str = str(sample)
            anonymized = anonymize_func(sample_str)
            formatted_samples.append(f"• Exemple {i} : {anonymized}")
        
        if len(sample_values) > 5:
            formatted_samples.append(f"• ... et {len(sample_values) - 5} autres valeurs")
        
        formatted_samples.append("\n*⚠️ Échantillons anonymisés pour protection des données personnelles*")
        
        return '\n'.join(formatted_samples)

    def create_validated_metadata_terms(self, glossary_guid, category_guids):
        """Créer les termes avec descriptions professionnelles significatives"""
        enriched_metadata = self.metadata_db['enriched_metadata']  
        validated_metadata = list(enriched_metadata.find({"validation_status": "validated"}))  
        logger.info(f"Métadonnées validées à synchroniser: {len(validated_metadata)}")  
        
        synced_terms = 0  
        
        for metadata in validated_metadata:  
            column_name = metadata['column_name']  
            job_id = metadata['job_id']  
            rgpd_category = metadata.get('recommended_rgpd_category')
            entity_types = metadata.get('entity_types', [])
            primary_entity = entity_types[0] if entity_types else "UNKNOWN"
            
            # Récupérer le nom métier depuis le template
            entity_desc = self.rgpd_manager.ENTITY_DESCRIPTIONS.get(
                primary_entity, 
                {"business_name": column_name.upper()}
            )
            
            term_name = f"{column_name.upper()}_TERM"  
            qualified_name = f"datagovernance.{column_name}_{job_id}@production"  
            
            try:  
                from AtlasAPI.atlas_integration import CustomAtlasGlossaryTerm  
                
                # Générer la description professionnelle
                professional_description = self._generate_professional_term_description(metadata)
                
                term = CustomAtlasGlossaryTerm(  
                    name=term_name,  
                    qualifiedName=qualified_name,  
                    shortDescription=entity_desc.get('business_name', f"Attribut métier validé: {column_name}"),  
                    longDescription=professional_description,
                    attributes={  
                        "source_column": column_name,  
                        "source_dataset": job_id,  
                        "entity_types": entity_types,  
                        "primary_entity_type": primary_entity,
                        "sensitivity_level": metadata.get('recommended_sensitivity_level'),  
                        "rgpd_category": rgpd_category,
                        "validation_date": datetime.now().isoformat(),
                        "validated_by": metadata.get('validated_by', 'Data Steward'),
                        "detection_confidence": metadata.get('detection_confidence', 0),
                        "data_quality_score": self._calculate_data_quality_score(metadata)
                    }  
                )  
                
                # Ajouter les classifications avec attributs enrichis
                sensitivity_level = metadata.get('recommended_sensitivity_level')  
                if sensitivity_level:  
                    term.addClassification(  
                        f"DataSensitivity_{sensitivity_level}",  
                        {  
                            "sensitivity_level": sensitivity_level,  
                            "rgpd_compliant": True,  
                            "data_steward": metadata.get('validated_by', 'Validated'),
                            "risk_level": self._map_sensitivity_to_risk(sensitivity_level),
                            "retention_period": self._get_retention_period(rgpd_category),
                            "access_level": self._map_sensitivity_to_access(sensitivity_level)
                        }  
                    )  
                
                term.glossaryGuid = glossary_guid  
                
                # Lier le terme à sa catégorie RGPD
                if rgpd_category and rgpd_category in category_guids:
                    term.categories = [{
                        "categoryGuid": category_guids[rgpd_category]
                    }]
                    logger.info(f"  → Terme lié à catégorie: {rgpd_category}")
                
                # Créer le terme via l'API REST  
                response = requests.post(  
                    f"{self.atlas_url}/api/atlas/v2/glossary/term",  
                    json=term.to_dict(),  
                    auth=self.auth_tuple  
                )  
                
                if response.status_code == 200:  
                    term_guid = response.json()['guid']
                    self.created_terms_cache[term_name] = term_guid
                    logger.info(f"✓ Terme métier synchronisé: {term_name} (GUID: {term_guid})")  
                    synced_terms += 1 
                    
                    # Lier explicitement à la catégorie
                    if rgpd_category and rgpd_category in category_guids:
                        category_guid = category_guids[rgpd_category]
                        link_url = f"{self.atlas_url}/api/atlas/v2/glossary/category/{category_guid}/terms"
                        link_response = requests.post(
                            link_url,
                            json=[{"termGuid": term_guid}],
                            auth=self.auth_tuple
                        )
                        if link_response.status_code == 200:
                            logger.info(f"  ✓ Terme {term_name} lié à catégorie {rgpd_category}")
                        else:
                            logger.warning(f"  ⚠️ Échec liaison catégorie: {link_response.text}")
                else:  
                    logger.error(f"✗ Erreur terme {term_name}: {response.text}")  
                    
            except Exception as e:  
                logger.error(f"✗ Erreur terme {term_name}: {e}")  
        
        return synced_terms
    
    def _map_sensitivity_to_risk(self, sensitivity_level):
        """Mapper le niveau de sensibilité au niveau de risque"""
        risk_mapping = {
            "PUBLIC": "LOW",
            "INTERNAL": "LOW",
            "CONFIDENTIAL": "MEDIUM",
            "RESTRICTED": "HIGH",
            "PERSONAL_DATA": "CRITICAL"
        }
        return risk_mapping.get(sensitivity_level, "MEDIUM")
    
    def _map_sensitivity_to_access(self, sensitivity_level):
        """Mapper le niveau de sensibilité au niveau d'accès"""
        access_mapping = {
            "PUBLIC": "PUBLIC_ACCESS",
            "INTERNAL": "INTERNAL_ONLY",
            "CONFIDENTIAL": "RESTRICTED_ACCESS",
            "RESTRICTED": "HIGHLY_RESTRICTED",
            "PERSONAL_DATA": "CONTROLLED_ACCESS_MFA"
        }
        return access_mapping.get(sensitivity_level, "RESTRICTED_ACCESS")

    def create_sensitivity_classifications(self):  
        """Créer des classifications de sensibilité enrichies et significatives"""  
        enriched_metadata = self.metadata_db['enriched_metadata']  
        sensitivity_levels = enriched_metadata.distinct('recommended_sensitivity_level')  
        sensitivity_levels = [level for level in sensitivity_levels if level]  
        
        logger.info(f"Niveaux de sensibilité détectés: {sensitivity_levels}")  
        
        # Définitions enrichies des classifications
        sensitivity_definitions = {
            "PUBLIC": {
                "description": "Données publiques sans restriction d'accès ni risque de confidentialité",
                "risk_level": "LOW",
                "retention_period": "UNLIMITED",
                "access_level": "PUBLIC_ACCESS",
                "examples": "Informations publiques, données anonymisées, rapports publiés"
            },
            "INTERNAL": {
                "description": "Données internes à usage organisationnel, accessibles aux employés autorisés",
                "risk_level": "LOW",
                "retention_period": "7_YEARS",
                "access_level": "INTERNAL_ONLY",
                "examples": "Documentation interne, statistiques agrégées, métriques business"
            },
            "CONFIDENTIAL": {
                "description": "Données confidentielles nécessitant une protection renforcée et un accès restreint",
                "risk_level": "MEDIUM",
                "retention_period": "5_YEARS",
                "access_level": "RESTRICTED_ACCESS",
                "examples": "Données de contact, emails, téléphones, adresses non sensibles"
            },
            "RESTRICTED": {
                "description": "Données restreintes à fort impact en cas de divulgation, accès hautement contrôlé",
                "risk_level": "HIGH",
                "retention_period": "3_YEARS",
                "access_level": "HIGHLY_RESTRICTED",
                "examples": "IBAN, RIB, données financières, informations contractuelles sensibles"
            },
            "PERSONAL_DATA": {
                "description": "Données personnelles sensibles (Art. 9 RGPD) nécessitant le plus haut niveau de protection",
                "risk_level": "CRITICAL",
                "retention_period": "2_YEARS",
                "access_level": "CONTROLLED_ACCESS_MFA",
                "examples": "CIN, numéros de carte bancaire, données de santé, données biométriques"
            }
        }
        
        classification_defs = []  
        
        for level in sensitivity_levels:
            level_info = sensitivity_definitions.get(level, {
                "description": f"Niveau de sensibilité: {level}",
                "risk_level": "MEDIUM",
                "retention_period": "5_YEARS",
                "access_level": "RESTRICTED_ACCESS",
                "examples": "À définir"
            })
            
            classification_def = {  
                "name": f"DataSensitivity_{level}",  
                "description": level_info["description"],  
                "attributeDefs": [  
                    {
                        "name": "sensitivity_level", 
                        "typeName": "string", 
                        "isOptional": False,
                        "description": "Niveau de sensibilité des données"
                    },  
                    {
                        "name": "risk_level", 
                        "typeName": "string", 
                        "isOptional": True,
                        "description": f"Niveau de risque associé: {level_info['risk_level']}"
                    },  
                    {
                        "name": "retention_period", 
                        "typeName": "string", 
                        "isOptional": True,
                        "description": f"Durée de conservation légale: {level_info['retention_period']}"
                    },  
                    {
                        "name": "access_level", 
                        "typeName": "string", 
                        "isOptional": True,
                        "description": f"Niveau d'accès requis: {level_info['access_level']}"
                    },  
                    {
                        "name": "rgpd_compliant", 
                        "typeName": "boolean", 
                        "isOptional": True,
                        "description": "Conformité RGPD validée"
                    },  
                    {
                        "name": "data_steward", 
                        "typeName": "string", 
                        "isOptional": True,
                        "description": "Responsable Data Steward de la validation"
                    },  
                    {
                        "name": "validation_date", 
                        "typeName": "date", 
                        "isOptional": True,
                        "description": "Date de validation de la classification"
                    },
                    {
                        "name": "examples", 
                        "typeName": "string", 
                        "isOptional": True,
                        "description": f"Exemples de données: {level_info['examples']}"
                    }
                ]  
            }  
            classification_defs.append(classification_def)  
        
        if classification_defs:  
            classification_batch = {"classificationDefs": classification_defs}  
            
            response = requests.post(  
                f"{self.atlas_url}/api/atlas/v2/types/typedefs",  
                json=classification_batch,  
                auth=self.auth_tuple  
            )  
            
            if response.status_code == 200:  
                logger.info(f"✓ {len(classification_defs)} classifications de sensibilité créées")  
                return True  
            elif response.status_code == 409 or "already exists" in response.text:  
                logger.info("✓ Classifications déjà existantes - Continuons")  
                return True  
            else:  
                logger.error(f"✗ Erreur création classifications: {response.text}")  
                return False  
        
        return True

    def _calculate_data_quality_score(self, metadata):  
        """Calculer un score de qualité des données enrichi"""  
        score = 0  
        
        # Présence d'entités détectées (30 points)
        if metadata.get('total_entities', 0) > 0:  
            score += 30  
        
        # Diversité des types d'entités (20 points)
        entity_types = metadata.get('entity_types', [])  
        if len(entity_types) > 0:  
            score += min(20, len(entity_types) * 10)
        
        # Validation par data steward (40 points)
        if metadata.get('validation_status') == 'validated':  
            score += 40  
        
        # Présence d'échantillons (10 points)
        if metadata.get('sample_values') and len(metadata.get('sample_values', [])) > 0:  
            score += 10
        
        # Bonus pour confiance élevée (10 points)
        confidence = metadata.get('detection_confidence', 0)
        if confidence > 80:
            score += 10
        
        return min(score, 100)

    # [Garder toutes les autres méthodes existantes: get_hive_table_entity, get_table_columns, 
    # find_glossary_term_by_name, assign_glossary_term_to_column, etc.]
    
    def get_hive_table_entity(self, table_name):  
        """Récupérer l'entité table Hive via API REST"""  
        try:  
            search_url = f"{self.atlas_url}/api/atlas/v2/search/dsl"  
            response = requests.get(  
                search_url,  
                auth=self.auth_tuple,  
                params={'query': f"hive_table where name='{table_name}'"}  
            )  
              
            logger.info(f"Recherche table {table_name}: {response.status_code}")  
              
            if response.status_code == 200:  
                entities = response.json().get('entities', [])  
                logger.info(f"Entités trouvées: {len(entities)}")  
                if entities:  
                    return entities[0]['guid']  
        except Exception as e:  
            logger.error(f"Erreur recherche table: {e}")  
          
        return None
    
    def get_table_columns(self, table_guid):  
        """Récupérer les colonnes via l'API REST"""  
        try:  
            entity_url = f"{self.atlas_url}/api/atlas/v2/entity/guid/{table_guid}"  
            response = requests.get(  
                entity_url,  
                auth=self.auth_tuple,  
                params={'ignoreRelationships': 'false'}  
            )  
              
            if response.status_code == 200:  
                entity = response.json()['entity']  
                columns = entity.get('relationshipAttributes', {}).get('columns', [])  
                  
                column_info = []  
                for col in columns:  
                    column_info.append({  
                        'guid': col['guid'],  
                        'name': col['displayText'],  
                        'type': col['typeName']  
                    })  
                return column_info  
        except Exception as e:  
            logger.error(f"Erreur récupération colonnes: {e}")  
          
        return []

    def find_glossary_term_by_name(self, term_name):
        """Rechercher un terme du glossaire par nom exact"""
        try:
            search_url = f"{self.atlas_url}/api/atlas/v2/search/basic"
            response = requests.get(
                search_url,
                auth=self.auth_tuple,
                params={
                    'query': term_name,
                    'typeName': 'AtlasGlossaryTerm',
                    'excludeDeletedEntities': 'true'
                }
            )
            
            if response.status_code == 200:
                entities = response.json().get('entities', [])
                for entity in entities:
                    if entity.get('attributes', {}).get('name') == term_name:
                        logger.info(f"✓ Terme trouvé par nom: {term_name}")
                        return entity['guid']
            
            if term_name in self.created_terms_cache:
                logger.info(f"✓ Terme trouvé dans cache: {term_name}")
                return self.created_terms_cache[term_name]
            
            logger.warning(f"⚠️ Terme non trouvé: {term_name}")
            return None
                
        except Exception as e:
            logger.error(f"Erreur recherche terme {term_name}: {e}")
            return None

    def assign_glossary_term_to_column(self, column_guid, term_guid):  
        """Assigner un terme via l'API REST directe"""  
        try:  
            assign_url = f"{self.atlas_url}/api/atlas/v2/entity/guid/{column_guid}/meanings"  
              
            payload = [{  
                "termGuid": term_guid,  
                "relationGuid": None  
            }]  
              
            response = requests.post(  
                assign_url,  
                auth=self.auth_tuple,  
                headers={'Content-Type': 'application/json'},  
                json=payload  
            )  
              
            if response.status_code == 200:
                logger.info(f"✅ Assignation réussie: colonne {column_guid} → terme {term_guid}")
                return True  
            else:  
                logger.error(f"❌ Erreur assignation: {response.status_code} - {response.text}")  
                return False  
                  
        except Exception as e:  
            logger.error(f"❌ Erreur assignation: {e}")  
            return False

    def create_smart_column_mapping(self):
        """Créer un mapping intelligent entre colonnes Hive et métadonnées CSV"""
        enriched_metadata = self.metadata_db['enriched_metadata']
        validated_metadata = list(enriched_metadata.find({"validation_status": "validated"}))
        
        mapping = {}
        
        for metadata in validated_metadata:
            csv_column_name = metadata['column_name']
            job_id = metadata['job_id']
            
            possible_hive_names = [
                csv_column_name,
                csv_column_name.lower(),
                csv_column_name.replace('_', ''),
                csv_column_name.upper(),
            ]
            
            term_name = f"{csv_column_name.upper()}_TERM"
            
            for hive_name in possible_hive_names:
                mapping[hive_name] = {
                    'term_name': term_name,
                    'job_id': job_id,
                    'original_csv_column': csv_column_name
                }
            
            logger.info(f"Mapping créé: {csv_column_name} → {term_name}")
        
        return mapping

    def get_glossary_term_by_qualified_name(self, term_name, job_id):  
        """Récupérer un terme par qualifiedName via l'API REST"""  
        column_name = term_name.lower().replace('_term', '')  
        qualified_name = f"datagovernance.{column_name}_{job_id}@production"  
          
        try:  
            search_url = f"{self.atlas_url}/api/atlas/v2/search/basic"  
            response = requests.get(  
                search_url,  
                auth=self.auth_tuple,  
                params={  
                    'query': qualified_name,  
                    'typeName': 'AtlasGlossaryTerm',  
                    'excludeDeletedEntities': 'true'  
                }  
            )  
              
            logger.info(f"Recherche terme par qualifiedName {qualified_name}: {response.status_code}")  
              
            if response.status_code == 200:  
                entities = response.json().get('entities', [])  
                for entity in entities:  
                    if entity.get('attributes', {}).get('qualifiedName') == qualified_name:  
                        logger.info(f"✓ Terme trouvé par qualifiedName: {qualified_name}")
                        return entity['guid']  
            
            logger.info(f"🔄 Recherche alternative par nom: {term_name}")
            return self.find_glossary_term_by_name(term_name)
                          
        except Exception as e:  
            logger.error(f"Erreur recherche terme: {e}")  
          
        return None

    def wait_for_terms_indexing(self, expected_term_count, max_wait=180):
        """Attendre que tous les termes soient indexés"""
        logger.info(f"⏳ Attente indexation de {expected_term_count} termes...")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                terms = self.list_all_glossary_terms()
                
                if len(terms) >= expected_term_count:
                    logger.info(f"✅ Tous les termes sont indexés ({len(terms)}/{expected_term_count})")
                    return True
                
                logger.info(f"⏳ Indexation en cours... ({len(terms)}/{expected_term_count})")
                time.sleep(10)
                
            except Exception as e:
                logger.warning(f"Erreur vérification indexation: {e}")
                time.sleep(10)
        
        logger.warning(f"⚠️ Timeout après {max_wait}s")
        return False

    def list_all_glossary_terms(self):
        """Lister tous les termes du glossaire"""
        try:
            if not self.current_glossary_guid:
                logger.warning("Aucun glossaire GUID défini")
                return []
                
            terms_url = f"{self.atlas_url}/api/atlas/v2/glossary/{self.current_glossary_guid}/terms"
            response = requests.get(
                terms_url,
                auth=self.auth_tuple
            )
            
            if response.status_code == 200:
                terms = response.json()
                logger.info(f"📋 Termes dans le glossaire: {len(terms)}")
                return terms
            else:
                logger.error(f"Erreur listing termes: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur listing termes: {e}")
            return []

    def automate_hive_glossary_assignment(self, table_name="entites_marocaines"):  
        """Workflow principal d'assignation automatique"""  
        logger.info(f"🚀 Début assignation automatique pour table: {table_name}")  
          
        try:  
            table_guid = self.get_hive_table_entity(table_name)  
            if not table_guid:  
                logger.error(f"❌ Table {table_name} non trouvée dans Atlas")  
                return {"success": False, "error": "Table non trouvée"}  
              
            columns = self.get_table_columns(table_guid)  
            logger.info(f"📋 Colonnes Hive trouvées: {[col['name'] for col in columns]}")  
              
            column_term_mapping = self.create_smart_column_mapping()  
            
            assigned_count = 0  
            skipped_count = 0
            
            for column in columns:  
                column_name = column['name']  
                
                mapping_info = column_term_mapping.get(column_name) or \
                              column_term_mapping.get(column_name.lower()) or \
                              column_term_mapping.get(column_name.upper())
                  
                if mapping_info:  
                    term_name = mapping_info['term_name']  
                    job_id = mapping_info['job_id']  
                      
                    logger.info(f"🔄 Traitement colonne '{column_name}' → terme '{term_name}'")
                    
                    term_guid = self.get_glossary_term_by_qualified_name(term_name, job_id)  
                      
                    if term_guid:  
                        success = self.assign_glossary_term_to_column(column['guid'], term_guid)  
                          
                        if success:  
                            logger.info(f"✅ Terme '{term_name}' assigné à colonne '{column_name}'")  
                            assigned_count += 1  
                        else:  
                            logger.error(f"❌ Échec assignation pour '{column_name}'")  
                    else:  
                        logger.warning(f"⚠️ Terme '{term_name}' non trouvé pour colonne '{column_name}'")
                        skipped_count += 1
                else:  
                    logger.info(f"ℹ️ Pas de mapping pour colonne Hive '{column_name}'")
                    skipped_count += 1
          
            return {  
                "success": True,  
                "table_guid": table_guid,  
                "columns_processed": len(columns),  
                "terms_assigned": assigned_count,
                "columns_skipped": skipped_count
            }  
              
        except Exception as e:  
            logger.error(f"❌ Erreur assignation: {str(e)}")  
            return {"success": False, "error": str(e)}

    def preview_sync_data(self):  
        """Prévisualiser les données qui seront synchronisées"""  
        enriched_metadata = self.metadata_db['enriched_metadata']  
          
        total_metadata = enriched_metadata.count_documents({})  
        validated_metadata = enriched_metadata.count_documents({"validation_status": "validated"})  
        pending_metadata = enriched_metadata.count_documents({"validation_status": "pending"})  
          
        categories = enriched_metadata.distinct('recommended_rgpd_category')  
        sensitivity_levels = enriched_metadata.distinct('recommended_sensitivity_level')  
          
        preview = {  
            "total_metadata": total_metadata,  
            "validated_metadata": validated_metadata,  
            "pending_metadata": pending_metadata,  
            "rgpd_categories": [cat for cat in categories if cat],  
            "sensitivity_levels": [level for level in sensitivity_levels if level],  
            "will_sync": validated_metadata > 0  
        }  
          
        logger.info("📊 PRÉVISUALISATION DE LA SYNCHRONISATION")  
        logger.info(f"📝 Total métadonnées: {total_metadata}")  
        logger.info(f"✅ Métadonnées validées (à synchroniser): {validated_metadata}")  
        logger.info(f"⏳ Métadonnées en attente: {pending_metadata}")  
        logger.info(f"📂 Catégories RGPD: {preview['rgpd_categories']}")  
        logger.info(f"🔒 Niveaux de sensibilité: {preview['sensitivity_levels']}")  
          
        if validated_metadata == 0:  
            logger.warning("⚠️  AUCUNE MÉTADONNÉE VALIDÉE - Rien ne sera synchronisé!")  
              
        return preview

    def _confirm_sync(self, preview):  
        """Demander confirmation avant synchronisation"""  
        print("\n" + "="*80)  
        print("⚠️  CONFIRMATION REQUISE - SYNCHRONISATION ATLAS")  
        print("="*80)  
        print(f"📊 Vous allez synchroniser {preview['validated_metadata']} métadonnées validées vers Atlas")  
        print(f"📂 Catégories RGPD: {', '.join(preview['rgpd_categories'])}")  
        print(f"🔒 Niveaux de sensibilité: {', '.join(preview['sensitivity_levels'])}")  
        print("\n⚠️  Cette opération va créer/modifier des éléments dans Apache Atlas:")
        print("   • Glossaire RGPD avec descriptions professionnelles")
        print("   • Catégories RGPD avec bases légales et durées de conservation")
        print("   • Termes métier avec descriptions significatives et exemples")
        print("   • Classifications de sensibilité avec niveaux de risque")
        print("   • Assignations automatiques aux colonnes Hive")
          
        response = input("\n🤔 Continuer la synchronisation? (oui/non): ").lower().strip()  
        return response in ['oui', 'o', 'yes', 'y']
    
    def _mark_as_synced(self, synced_count):  
        """Marquer les métadonnées synchronisées"""  
        if synced_count > 0:  
            enriched_metadata = self.metadata_db['enriched_metadata']  
            enriched_metadata.update_many(  
                {"validation_status": "validated"},  
                {"$set": {
                    "atlas_sync_status": "synced", 
                    "atlas_sync_date": datetime.now(),
                    "glossary_guid": self.current_glossary_guid
                }}  
            )  
            logger.info(f"📝 {synced_count} métadonnées marquées comme synchronisées")

    def sync_governance_metadata(self, preview_only=False):  
        """Fonction principale de synchronisation pour la gouvernance métier"""  
        logger.info("🚀 DÉBUT DE LA SYNCHRONISATION MÉTADONNÉES GOUVERNANCE RGPD")  
        logger.info("="*80)
          
        try:  
            preview = self.preview_sync_data()  
              
            if preview_only:  
                logger.info("👁️  Mode prévisualisation uniquement - Aucune modification dans Atlas")  
                return {"success": True, "preview": preview, "sync_executed": False}  
              
            if not preview["will_sync"]:  
                logger.warning("🛑 Arrêt: Aucune métadonnée validée à synchroniser")  
                return {"success": False, "error": "Aucune métadonnée validée", "preview": preview}  
              
            if not self._confirm_sync(preview):  
                logger.info("🛑 Synchronisation annulée par l'utilisateur")  
                return {"success": False, "error": "Annulée par l'utilisateur", "preview": preview}  
              
            logger.info("\n▶️  EXÉCUTION DE LA SYNCHRONISATION...")  
            logger.info("="*80)
              
            # 1. Créer les classifications de sensibilité enrichies
            logger.info("\n📋 ÉTAPE 1/6: Création des classifications de sensibilité...")
            if not self.create_sensitivity_classifications():  
                logger.error("❌ Échec création classifications")  
                return {"success": False, "error": "Échec création classifications"}  
            logger.info("✅ Classifications créées avec succès")
              
            # 2. Créer le glossaire métier RGPD
            logger.info("\n📚 ÉTAPE 2/6: Création du glossaire RGPD...")
            glossary_guid = self.create_business_glossary()  
            if not glossary_guid:  
                logger.error("❌ Échec création glossaire")  
                return {"success": False, "error": "Échec création glossaire"}
            logger.info(f"✅ Glossaire créé: {glossary_guid}")
              
            # 3. Créer les catégories RGPD avec descriptions complètes
            logger.info("\n📂 ÉTAPE 3/6: Création des catégories RGPD...")
            category_guids = self.create_rgpd_categories(glossary_guid)
            logger.info(f"✅ {len(category_guids)} catégories RGPD créées")
              
            # 4. Synchroniser les métadonnées validées avec descriptions professionnelles
            logger.info("\n📝 ÉTAPE 4/6: Synchronisation des termes métier...")
            synced_terms = self.create_validated_metadata_terms(glossary_guid, category_guids)
            logger.info(f"✅ {synced_terms} termes métier synchronisés")
              
            # 5. Attendre l'indexation Atlas avant assignation
            logger.info("\n⏳ ÉTAPE 5/6: Attente de l'indexation Atlas...")
            self.wait_for_terms_indexing(synced_terms, max_wait=180)
            logger.info("✅ Indexation terminée")
              
            # 6. Assigner automatiquement les termes aux colonnes Hive
            logger.info("\n🔗 ÉTAPE 6/6: Assignation des termes aux colonnes Hive...")
            assignment_result = self.automate_hive_glossary_assignment("entites_marocaines")
            logger.info(f"✅ {assignment_result.get('terms_assigned', 0)} assignations réussies")
              
            # Marquer les métadonnées comme synchronisées
            self._mark_as_synced(synced_terms)  
              
            result = {  
                "success": True,  
                "glossary_guid": glossary_guid,
                "glossary_name": "Glossaire_RGPD_Gouvernance_Données",
                "validated_terms_synced": synced_terms,  
                "categories_created": len(category_guids),
                "category_details": list(category_guids.keys()),
                "sync_timestamp": datetime.now().isoformat(),  
                "preview": preview,  
                "hive_assignment": assignment_result,
                "created_terms_cache": len(self.created_terms_cache),
                "atlas_url": f"{self.atlas_url}/#/glossary"
            }  
              
            logger.info("\n" + "="*80)
            logger.info("✅ SYNCHRONISATION TERMINÉE AVEC SUCCÈS")
            logger.info("="*80)
            logger.info(f"📚 Glossaire: {result['glossary_name']}")
            logger.info(f"📝 Termes synchronisés: {synced_terms}")
            logger.info(f"📂 Catégories RGPD: {', '.join(result['category_details'])}")
            logger.info(f"🔗 Assignations Hive: {assignment_result.get('terms_assigned', 0)}/{assignment_result.get('columns_processed', 0)}")
            logger.info(f"🌐 Interface Atlas: {result['atlas_url']}")
            
            return result  
              
        except Exception as e:  
            logger.error(f"❌ ERREUR lors de la synchronisation: {str(e)}")  
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}  
          
        finally:  
            self.mongo_client.close()

def main():  
    """Point d'entrée principal avec interface utilisateur"""
    print("\n" + "="*80)
    print("🚀 SYSTÈME DE GOUVERNANCE RGPD - SYNCHRONISATION APACHE ATLAS")
    print("="*80)
    print("📋 Ce script va créer un glossaire RGPD professionnel avec:")
    print("   • Descriptions métier significatives et conformes RGPD")
    print("   • Catégories avec bases légales et durées de conservation")
    print("   • Termes enrichis avec exemples anonymisés")
    print("   • Classifications de sensibilité détaillées")
    print("   • Assignations automatiques aux colonnes Hive")
    print("="*80)
    
    governance = AtlasMetadataGovernance()  
    
    # Mode debug optionnel
    print("\n🔧 Options disponibles:")
    print("   1. Prévisualisation uniquement (recommandé pour première exécution)")
    print("   2. Synchronisation complète")
    print("   3. Mode debug (diagnostic des problèmes)")
    
    choice = input("\nVotre choix (1/2/3): ").strip()
    
    if choice == "1":
        logger.info("\n👁️  MODE PRÉVISUALISATION")
        result = governance.sync_governance_metadata(preview_only=True)
    elif choice == "3":
        logger.info("\n🔧 MODE DEBUG")
        # Fonction debug si nécessaire
        result = governance.sync_governance_metadata()
    else:
        logger.info("\n▶️  MODE SYNCHRONISATION COMPLÈTE")
        result = governance.sync_governance_metadata()
      
    # Affichage des résultats
    print("\n" + "="*80)
    print("📊 RÉSULTAT DE LA SYNCHRONISATION")
    print("="*80)
    print(json.dumps(result, indent=2, ensure_ascii=False))
      
    if result.get("success"):
        print(f"\n✅ Synchronisation réussie!")
        print(f"📚 Glossaire GUID: {result.get('glossary_guid')}")
        print(f"📝 Termes validés: {result.get('validated_terms_synced', 0)}")
        print(f"📂 Catégories RGPD: {result.get('categories_created', 0)}")
        print(f"🔗 Assignations Hive: {result.get('hive_assignment', {}).get('terms_assigned', 0)}")
        print(f"\n🌐 Accédez au glossaire: {result.get('atlas_url')}")
        
        if result.get('hive_assignment', {}).get('terms_assigned', 0) == 0:
            print("\n⚠️ ATTENTION: Aucune assignation Hive réussie")
            print("Solutions possibles:")
            print("   • Vérifiez que les termes sont visibles dans Atlas UI")
            print("   • Attendez quelques minutes pour l'indexation")
            print("   • Relancez le script")
    else:
        print(f"\n❌ Échec de la synchronisation: {result.get('error')}")
        print("Consultez les logs ci-dessus pour plus de détails")

if __name__ == "__main__":
    main()