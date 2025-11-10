from django.shortcuts import render, redirect        
from django.http import HttpResponse, JsonResponse        
from django.views import View        
from pymongo import MongoClient        
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine        
from presidio_anonymizer.entities import OperatorConfig        
import pandas as pd        
from presidio_structured import StructuredEngine, PandasAnalysisBuilder        
import csv   
import asyncio  
import io    
import traceback    
from .quality_analyzer import DataQualityAnalyzer
import json       
import google.generativeai as genai
import psutil
import re
from multiprocessing import Pool, cpu_count
import numpy as np
from db_connections import db as main_db          
import datetime          
from bson import ObjectId        
from semantic_engine import SemanticAnalyzer, IntelligentAutoTagger    
from presidio_custom import create_enhanced_analyzer_engine    
import os
from recommendation_engine.MoteurDeRecommandationAvecDeepSeekML import IntelligentRecommendationEngine, GeminiClient
from gridfs import GridFS  
from recommendation_engine.recommendation_engine_core import EnterpriseRecommendationEngine  


# Configuration centralisée des entités à exclure    
EXCLUDED_ENTITY_TYPES = {    
    'IN_PAN', 'URL', 'DOMAIN_NAME', 'NRP', 'US_BANK_NUMBER',    
    'IN_AADHAAR', 'US_DRIVER_LICENSE', 'UK_NHS'    
}    
    
from db_connections import db as main_db      
# Ajoutez cette ligne :      
users = main_db["users"]    
# Connexion à MongoDB pour les données CSV        
client = MongoClient('mongodb://mongodb:27017/')        
csv_db = client['csv_anonymizer_db']        
collection = csv_db['csv_data']        
        
fs = GridFS(csv_db)
        
class UploadCSVView(View):  
 def get(self, request):  
        if not request.session.get("user_email"):  
            return redirect('login_form')  
          
        # Vérification du rôle  
        user_email = request.session.get("user_email")  
        user = users.find_one({'email': user_email})  
          
        if user and user.get('role') != 'admin':  
            return redirect('authapp:home')  
          
        return render(request, 'csv_anonymizer/upload.html')  
  
 def post(self, request):
    """Upload CSV avec analyse de qualité complète"""
    print("=== DÉBUT UPLOAD CSV AVEC ANALYSE QUALITÉ ===")
    user_email = request.session.get("user_email")
    print(f"User email: {user_email}")
    
    # ========================================
    # VÉRIFICATIONS D'AUTHENTIFICATION
    # ========================================
    if not user_email:
        print("ERREUR: Aucun email utilisateur trouvé")
        return redirect('login_form')
    
    user = users.find_one({'email': user_email})
    print(f"Utilisateur trouvé: {user}")
    
    if user and user.get('role') != 'admin':
        print(f"ERREUR: Rôle utilisateur incorrect: {user.get('role')}")
        return redirect('authapp:home')
    
    # ========================================
    # VALIDATION DU FICHIER
    # ========================================
    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        print("ERREUR: Aucun fichier CSV fourni")
        return render(request, 'csv_anonymizer/upload.html', {'error': 'Aucun fichier sélectionné'})
    
    print(f"Fichier reçu: {csv_file.name}, taille: {csv_file.size} bytes")
    
    if not csv_file.name.endswith('.csv'):
        print(f"ERREUR: Format de fichier incorrect: {csv_file.name}")
        return render(request, 'csv_anonymizer/upload.html', {'error': 'Le fichier doit être au format CSV'})
    
    # ========================================
    # TRAITEMENT PAR STREAMING
    # ========================================
    print("Début traitement par streaming...")
    content_bytes = b''
    chunk_count = 0
    
    for chunk in csv_file.chunks():
        content_bytes += chunk
        chunk_count += 1
    
    print(f"Streaming terminé: {chunk_count} chunks traités")
    
    # ========================================
    # DÉCODAGE MULTI-ENCODAGE
    # ========================================
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    content = None
    
    for encoding in encodings:
        try:
            content = content_bytes.decode(encoding)
            print(f"Décodage réussi avec: {encoding}")
            break
        except UnicodeDecodeError:
            continue
    
    if content is None:
        content = content_bytes.decode('utf-8', errors='replace')
        print("ATTENTION: Décodage avec remplacement de caractères invalides")
    
    print(f"Contenu total: {len(content)} caractères")
    
    # ========================================
    # PARSING CSV ET EXTRACTION HEADERS
    # ========================================
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    print(f"Headers détectés: {headers}")
    
    # ========================================
    # STOCKAGE GRIDFS
    # ========================================
    print("Stockage GridFS...")
    try:
        file_id = fs.put(
            io.BytesIO(content.encode('utf-8')),
            filename=csv_file.name,
            content_type='text/csv',
            upload_date=datetime.datetime.now()
        )
        print(f"Fichier stocké dans GridFS avec ID: {file_id}")
    except Exception as e:
        print(f"ERREUR GridFS: {e}")
        return render(request, 'csv_anonymizer/upload.html', {'error': f'Erreur de stockage: {e}'})
    
    # ========================================
    # RÉCUPÉRATION DATA STEWARDS
    # ========================================
    print("Récupération des data stewards...")
    data_stewards = list(users.find({'role': 'user'}))
    authorized_emails = [ds['email'] for ds in data_stewards]
    print(f"Data stewards trouvés: {len(data_stewards)}, emails: {authorized_emails}")
    
    # ========================================
    # CRÉATION DU JOB
    # ========================================
    print("Création du job...")
    job_data = {
        'user_email': request.session.get('user_email'),
        'original_filename': csv_file.name,
        'gridfs_file_id': file_id,
        'upload_date': datetime.datetime.now(),
        'status': 'pending',
        'shared_with_data_stewards': True,
        'authorized_users': authorized_emails
    }
    
    try:
        result = main_db.anonymization_jobs.insert_one(job_data)
        job_id = result.inserted_id
        print(f"Job créé avec ID: {job_id}")
    except Exception as e:
        print(f"ERREUR création job: {e}")
        return render(request, 'csv_anonymizer/upload.html', {'error': f'Erreur de création du job: {e}'})
    
    # ========================================
    # CHARGEMENT COMPLET DES DONNÉES
    # ========================================
    print("🔄 Chargement COMPLET du dataset pour analyse qualité...")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)  # Skip headers again
    
    all_rows = []
    for row in reader:
        if len(row) == len(headers):  # Vérifier cohérence
            row_dict = {headers[i]: row[i] for i in range(len(headers))}
            all_rows.append(row_dict)
    
    print(f"✅ Dataset chargé: {len(all_rows)} lignes")
    
    # ========================================
    # ANALYSE DE QUALITÉ COMPLÈTE (NOUVEAU)
    # ========================================
    print("🔍 Début analyse de qualité...")
    try:
        
        quality_analyzer = DataQualityAnalyzer()
        quality_report = quality_analyzer.analyze_full_dataset(headers, all_rows)
        
        # Sauvegarder le rapport de qualité dans MongoDB
        print("💾 Sauvegarde du rapport de qualité...")
        main_db.quality_reports.update_one(
            {'job_id': str(job_id)},
            {
                '$set': {
                    'job_id': str(job_id),
                    'report': quality_report,
                    'created_at': datetime.datetime.now()
                }
            },
            upsert=True
        )
        
        print(f"""
        📊 RAPPORT DE QUALITÉ:
        - Score global: {quality_report['quality_score']}/10
        - Valeurs manquantes: {quality_report['missing_values']['total_missing']} ({quality_report['missing_values']['missing_percentage']}%)
        - Doublons: {quality_report['duplicates']['total_duplicates']} ({quality_report['duplicates']['duplicate_percentage']}%)
        - Incohérences: {quality_report['inconsistencies']['total_inconsistencies']}
        - Problèmes critiques: {len(quality_report['critical_issues'])}
        """)
        
        # Afficher les problèmes critiques
        if quality_report['critical_issues']:
            print("\n⚠️ PROBLÈMES CRITIQUES DÉTECTÉS:")
            for issue in quality_report['critical_issues']:
                print(f"  - [{issue['severity']}] {issue['message']}")
                print(f"    Action: {issue['action']}")
    
    except Exception as e:
        print(f"⚠️ ERREUR analyse qualité: {e}")
        import traceback
        traceback.print_exc()
        # Créer un rapport par défaut en cas d'erreur
        quality_report = {
            'quality_score': 5.0,
            'missing_values': {'total_missing': 0, 'missing_percentage': 0.0},
            'duplicates': {'total_duplicates': 0, 'duplicate_percentage': 0.0},
            'inconsistencies': {'total_inconsistencies': 0},
            'critical_issues': []
        }
    
    # ========================================
    # ANALYSE DES ENTITÉS SENSIBLES
    # ========================================
    print("\n🔍 Analyse des entités sensibles (échantillon de 50 lignes)...")
    sample_rows = all_rows[:50]  # Augmenté à 50 pour meilleure détection
    
    try:
        analyzer = create_enhanced_analyzer_engine("moroccan_entities_model_v2")
        semantic_analyzer = SemanticAnalyzer("moroccan_entities_model_v2")
        auto_tagger = IntelligentAutoTagger(analyzer, semantic_analyzer)
        print("Analyseurs initialisés avec succès")
    except Exception as e:
        print(f"ERREUR initialisation analyseurs: {e}")
        return render(request, 'csv_anonymizer/upload.html', {'error': f'Erreur d\'initialisation: {e}'})
    
    detected_entities = set()
    entity_count = 0
    
    for row_idx, row in enumerate(sample_rows):
        if row_idx % 10 == 0:
            print(f"Analyse ligne {row_idx + 1}/{len(sample_rows)}")
        
        for header, value in row.items():
            if isinstance(value, str) and value.strip():
                try:
                    entities, tags = auto_tagger.analyze_and_tag(value, dataset_name=csv_file.name)
                    for entity in entities:
                        if entity.entity_type not in EXCLUDED_ENTITY_TYPES:
                            detected_entities.add(entity.entity_type)
                            entity_count += 1
                except Exception as e:
                    pass  # Continuer même en cas d'erreur
    
    print(f"✅ Analyse entités terminée: {entity_count} entités trouvées")
    print(f"Types d'entités détectées: {list(detected_entities)}")
    
    # ========================================
    # SAUVEGARDE EN CHUNKS
    # ========================================
    print("\n💾 Début sauvegarde en chunks...")
    chunk_size = 1000
    chunk_number = 0
    
    for i in range(0, len(all_rows), chunk_size):
        chunk_data = all_rows[i:i + chunk_size]
        # Convertir dictionnaires en listes pour _save_chunk
        chunk_as_lists = [[row[h] if h in row else '' for h in headers] for row in chunk_data]
        self._save_chunk(job_id, chunk_number, headers, chunk_as_lists)
        print(f"Chunk {chunk_number} sauvegardé: {len(chunk_data)} lignes")
        chunk_number += 1
    
    print(f"✅ Sauvegarde chunks terminée: {chunk_number} chunks, {len(all_rows)} lignes totales")
    
    # ========================================
    # GÉNÉRATION RECOMMANDATIONS IA
    # ========================================
    print("\n🤖 === DÉBUT GÉNÉRATION RECOMMANDATIONS IA ===")
    has_recommendations = False
    
    try:
        # Vérification mémoire
        memory = psutil.virtual_memory()
        print(f"Mémoire disponible: {memory.available // (1024**2)} MB")
        
        if memory.percent > 90:
            print("ALERTE: Mémoire critique - utilisation recommandations par défaut")
            raise Exception("Mémoire insuffisante")
        
        # Vérification API Key
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        print(f"API Key: {'Configurée' if gemini_api_key else 'Manquante'}")
        
        if not gemini_api_key:
            print("ERREUR: API Key manquante")
            raise Exception("API Key manquante")
        
        # Import avec gestion d'erreurs
        try:
            import google.generativeai as genai
            print("Import genai: OK")
        except ImportError as e:
            print(f"Import genai échoué: {e}")
            raise Exception("Module genai non disponible")
        
        # Configuration genai
        print("Configuration genai...")
        genai.configure(api_key=gemini_api_key)
        
        # Créer une instance du client Gemini synchrone
        class SyncGeminiClient:
            def __init__(self, api_key):
                self.api_key = api_key
                self.model = genai.GenerativeModel('gemini-2.5-flash')
            
            def generate_content_sync(self, prompt):
                """Génération synchrone de contenu"""
                try:
                    generation_config = genai.types.GenerationConfig(
                        candidate_count=1,
                        max_output_tokens=2048,
                        temperature=0.7
                    )
                    
                    response = self.model.generate_content(
                        prompt,
                        generation_config=generation_config
                    )
                    
                    if response and response.text:
                        return response.text
                    return None
                except Exception as e:
                    print(f"Erreur génération Gemini: {e}")
                    raise
        
        # Initialiser le client synchrone
        sync_client = SyncGeminiClient(gemini_api_key)
        print("Client Gemini synchrone initialisé")
        
        # Créer le profil du dataset
        print("Création du profil dataset...")
        enterprise_engine = EnterpriseRecommendationEngine(sync_client)
        
        dataset_profile = enterprise_engine.create_dataset_profile_from_presidio(
            str(job_id), 
            detected_entities, 
            headers, 
            sample_rows
        )
        print(f"Profil dataset créé: {dataset_profile.get('name', 'Dataset')}")
        
        # Générer les recommandations de manière synchrone
        print("Génération recommandations par catégorie...")
        recommendations_by_category = {}
        
        print("Mode SMART: Génération sans Gemini (quota épuisé)...")
        
        for category in enterprise_engine.categories:
            print(f"Génération SMART pour {category}...")
            try:
                # Essayer d'abord avec vos templates (si quota disponible)
                recs = self._generate_category_recommendations_sync_optimized(
                    enterprise_engine, 
                    sync_client, 
                    dataset_profile, 
                    category
                )
            except Exception as e:
                print(f"Fallback SMART pour {category}: {e}")
                # Utiliser la génération intelligente sans Gemini
                recs = self._generate_smart_recommendations_without_gemini(
                    enterprise_engine,
                    dataset_profile, 
                    category
                )
            
            recommendations_by_category[category] = recs
            print(f"Recommandations {category}: {len(recs)} générées")
        
        # Formater le résultat final
        comprehensive_recommendations = enterprise_engine._format_enterprise_output(recommendations_by_category)
        
        # Sauvegarder les recommandations dans MongoDB
        print("Sauvegarde des recommandations...")
        recommendations_data = {
            'job_id': str(job_id),
            'recommendations': [rec.__dict__ for rec in comprehensive_recommendations['recommendations']],
            'category_summary': comprehensive_recommendations['category_summary'],
            'overall_score': comprehensive_recommendations['overall_score'],
            'created_at': datetime.datetime.now(),
            'source': 'gemini_sync'
        }
        
        main_db.job_recommendations.insert_one(recommendations_data)
        
        has_recommendations = len(comprehensive_recommendations['recommendations']) > 0
        print(f"Recommandations sauvegardées: {len(comprehensive_recommendations['recommendations'])}")
    
    except Exception as e:
        print(f"ERREUR génération recommandations: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        has_recommendations = False
    
    print(f"=== FIN GÉNÉRATION RECOMMANDATIONS: {has_recommendations} ===")
    
    # ========================================
    # SAUVEGARDE SESSION
    # ========================================
    request.session['current_job_id'] = str(job_id)
    print(f"Job ID sauvegardé dans session: {str(job_id)}")
    
    # ========================================
    # RENDU FINAL
    # ========================================
    print(f"\n✅ === UPLOAD TERMINÉ AVEC SUCCÈS ===")
    print(f"Job ID: {job_id}")
    print(f"Score qualité: {quality_report['quality_score']}/10")
    print(f"Entités détectées: {len(detected_entities)} types")
    print(f"Headers: {len(headers)} colonnes")
    print(f"Total lignes: {len(all_rows)}")
    print(f"Recommandations: {has_recommendations}")
    
    return render(request, 'csv_anonymizer/select_entities.html', {
        'job_id': str(job_id),
        'detected_entities': list(detected_entities),
        'headers': headers,
        'has_recommendations': has_recommendations,
        'quality_report': quality_report,  # NOUVEAU: rapport de qualité complet
        'has_quality_issues': quality_report['quality_score'] < 7.0  # NOUVEAU: indicateur problèmes
    })
 def _generate_category_recommendations_sync_optimized(self, enterprise_engine, sync_client, dataset_profile, category):  
    """Version optimisée de génération par catégorie"""  
      
    # Templates simplifiés intégrés  
    simple_templates = {  
        'COMPLIANCE': "Analysez conformité RGPD pour {dataset_name} avec entités {personal_entities}. Score: {compliance_score}. JSON uniquement: {{'compliance_score': 7, 'critical_gaps': ['gap1'], 'regulatory_risk': 'HIGH'}}",  
        'SECURITY': "Risques sécurité pour entités {sensitive_entities}, niveau {risk_level}. JSON: {{'risk_level': 'HIGH', 'encryption_needs': ['col1'], 'access_controls': ['ctrl1']}}",  
        'QUALITY': "Qualité données {dataset_name}: {missing_percentage}% manquantes, {duplicate_count} doublons. JSON: {{'quality_score': 6, 'data_issues': ['issue1']}}",  
        'GOVERNANCE': "Gouvernance {dataset_name}: {total_rows} lignes, {headers_count} colonnes. JSON: {{'governance_score': 5, 'missing_metadata': ['meta1']}}"  
    }  
      
    template = simple_templates.get(category)  
    if not template:  
        return enterprise_engine._create_default_recommendations(category, dataset_profile)  
      
    try:  
        # Préparer données template  
        template_data = enterprise_engine._prepare_template_data(dataset_profile, category)  
        prompt = template.format(**template_data)  
          
        # Appel Gemini avec timeout court  
        response = sync_client.generate_content_sync(prompt)  
          
        if response:  
            return enterprise_engine._parse_gemini_response(response, category, dataset_profile)  
        else:  
            return enterprise_engine._create_default_recommendations(category, dataset_profile)  
              
    except Exception as e:  
        print(f"Erreur génération optimisée {category}: {e}")  
        return enterprise_engine._create_default_recommendations(category, dataset_profile)
    
 def _generate_category_recommendations_sync(self, enterprise_engine, sync_client, dataset_profile, category):
    """Génère des recommandations pour une catégorie de manière synchrone"""
    try:
        # Essayer plusieurs imports possibles
        try:
            from csv_anonymizer.recommendation_templates import ENTERPRISE_TEMPLATES
        except ImportError:
            from .recommendation_templates import ENTERPRISE_TEMPLATES
    except ImportError:
        print(f"ERREUR IMPORT: Impossible d'importer recommendation_templates")
        # Utiliser les recommandations par défaut
        return enterprise_engine._create_default_recommendations(category, dataset_profile)
    
    template = ENTERPRISE_TEMPLATES.get(category, "")
    
    if not template:
        print(f"Pas de template pour {category}, utilisation des recommandations par défaut")
        return enterprise_engine._create_default_recommendations(category, dataset_profile)
    
    # Préparer les données pour le template
    template_data = enterprise_engine._prepare_template_data(dataset_profile, category)
    prompt = template.format(**template_data)
    
    try:
        # Générer avec Gemini de manière synchrone
        print(f"Appel Gemini pour {category}...")
        response = sync_client.generate_content_sync(prompt)
        
        if response:
            print(f"Réponse Gemini reçue pour {category}: {len(response)} caractères")
            # Parser la réponse
            return enterprise_engine._parse_gemini_response(response, category, dataset_profile)
        else:
            print(f"Pas de réponse Gemini pour {category}")
            return enterprise_engine._create_default_recommendations(category, dataset_profile)
            
    except Exception as e:
        print(f"Erreur appel Gemini pour {category}: {e}")
        return enterprise_engine._create_default_recommendations(category, dataset_profile)
    
 def _generate_smart_recommendations_without_gemini(self, enterprise_engine, dataset_profile, category):
    """Génère des recommandations intelligentes basées sur l'analyse des données sans appeler Gemini"""
    from datetime import datetime
    from .models import RecommendationItem
    
    detected_entities = set(dataset_profile.get('detected_entities', []))
    quality_issues = dataset_profile.get('quality_issues', {})
    compliance_status = dataset_profile.get('compliance_status', {})
    security_risks = dataset_profile.get('security_risks', {})
    
    recommendations = []
    
    if category == 'COMPLIANCE':
        # Simuler la réponse JSON que Gemini aurait donnée
        compliance_score = compliance_status.get('compliance_score', 5.0)
        has_personal_data = bool(detected_entities & {'PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'ID_MAROC'})
        
        if has_personal_data:
            # Recommandation principale RGPD
            rec = RecommendationItem(
                id=f"compliance_{dataset_profile.get('dataset_id')}_rgpd_smart",
                title="Conformité RGPD - Documentation obligatoire",
                description=f"Entités personnelles détectées: {', '.join(detected_entities & {'PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'ID_MAROC'})}. Actions immédiates: 1) Tenir un registre des traitements (art. 30 RGPD), 2) Informer les personnes concernées (art. 13-14), 3) Mettre en place les droits (art. 15-22), 4) Désigner un DPO si requis (art. 37).",
                category="COMPLIANCE",
                priority=9.2,
                confidence=0.95,
                metadata={
                    'compliance_score': compliance_score,
                    'critical_gaps': ["Registre des traitements manquant", "Information des personnes insuffisante", "Droits RGPD non implémentés"],
                    'immediate_actions': ["Créer registre RGPD", "Rédiger mentions d'information", "Implémenter droit d'accès"],
                    'regulatory_risk': 'HIGH',
                    'color': 'red',
                    'entities_detected': list(detected_entities & {'PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'ID_MAROC'}),
                    'source': 'smart_analysis'
                },
                created_at=datetime.now()
            )
            recommendations.append(rec)
            
            # Recommandation sur les bases légales
            rec2 = RecommendationItem(
                id=f"compliance_{dataset_profile.get('dataset_id')}_legal_basis",
                title="Bases légales du traitement à définir",
                description="Chaque traitement de données personnelles doit avoir une base légale claire (art. 6 RGPD). Identifier si: consentement, contrat, obligation légale, intérêt vital, mission de service public, ou intérêt légitime.",
                category="COMPLIANCE",
                priority=8.5,
                confidence=0.90,
                metadata={
                    'color': 'orange',
                    'regulatory_requirement': 'RGPD Article 6',
                    'source': 'smart_analysis'
                },
                created_at=datetime.now()
            )
            recommendations.append(rec2)
    
    elif category == 'SECURITY':
        risk_level = security_risks.get('risk_level', 'MEDIUM')
        high_risk_entities = security_risks.get('high_risk_entities', [])
        
        if detected_entities & {'ID_MAROC', 'CREDIT_CARD', 'IBAN_CODE'} or risk_level == 'HIGH':
            rec = RecommendationItem(
                id=f"security_{dataset_profile.get('dataset_id')}_encryption_smart",
                title="Chiffrement obligatoire - Données critiques détectées",
                description=f"Entités à haut risque: {', '.join(high_risk_entities)}. Mesures de sécurité requises: 1) Chiffrement AES-256 au repos, 2) TLS 1.3 en transit, 3) Gestion des clés sécurisée (HSM/KMS), 4) Contrôles d'accès stricts (RBAC), 5) Audit trail complet, 6) Tests de pénétration réguliers.",
                category="SECURITY",
                priority=8.8,
                confidence=0.93,
                metadata={
                    'risk_level': risk_level,
                    'encryption_needs': list(detected_entities & {'ID_MAROC', 'CREDIT_CARD', 'IBAN_CODE', 'EMAIL_ADDRESS'}),
                    'access_controls': ["Authentification multi-facteurs", "Contrôle d'accès basé sur les rôles", "Chiffrement de bout en bout"],
                    'color': 'red',
                    'security_standards': ['ISO 27001', 'NIST Cybersecurity Framework'],
                    'immediate_actions': ['Audit de sécurité', 'Plan de chiffrement', 'Politique d\'accès'],
                    'source': 'smart_analysis'
                },
                created_at=datetime.now()
            )
            recommendations.append(rec)
    
    elif category == 'QUALITY':
        missing_pct = quality_issues.get('missing_percentage', 0)
        duplicate_count = quality_issues.get('duplicate_rows', 0)
        quality_score = max(1, 10 - missing_pct/5 - duplicate_count/10)
        
        if missing_pct > 5 or duplicate_count > 0:
            rec = RecommendationItem(
                id=f"quality_{dataset_profile.get('dataset_id')}_improvement_smart",
                title=f"Amélioration qualité requise - Score {quality_score:.1f}/10",
                description=f"Analyse détaillée: {missing_pct:.1f}% valeurs manquantes, {duplicate_count} doublons détectés. Plan d'amélioration: 1) Validation automatisée des formats, 2) Règles de complétude, 3) Déduplication intelligente, 4) Monitoring qualité en continu, 5) Alertes qualité automatiques.",
                category="QUALITY",
                priority=7.0 if missing_pct > 15 else 6.0,
                confidence=0.85,
                metadata={
                    'quality_score': quality_score,
                    'data_issues': [f"Valeurs manquantes: {missing_pct:.1f}%", f"Doublons: {duplicate_count}"],
                    'improvement_actions': ["Validation des formats", "Nettoyage des doublons", "Règles de complétude", "Monitoring continu"],
                    'color': 'yellow',
                    'data_profiling': {
                        'missing_percentage': missing_pct,
                        'duplicate_count': duplicate_count,
                        'consistency': quality_issues.get('data_consistency', 'unknown')
                    },
                    'source': 'smart_analysis'
                },
                created_at=datetime.now()
            )
            recommendations.append(rec)
    
    elif category == 'GOVERNANCE':
        headers_count = len(dataset_profile.get('headers', []))
        total_rows = dataset_profile.get('total_rows', 0)
        
        if headers_count > 5:
            governance_score = min(8, max(3, 8 - headers_count/5))
            rec = RecommendationItem(
                id=f"governance_{dataset_profile.get('dataset_id')}_documentation_smart",
                title=f"Gouvernance des données - Complexité élevée détectée",
                description=f"Dataset complexe: {headers_count} colonnes, {total_rows:,} lignes. Gouvernance requise: 1) Catalogue de données avec métadonnées, 2) Définition des propriétaires de données, 3) Classifications de sensibilité, 4) Règles de rétention, 5) Workflows d'approbation, 6) Traçabilité des modifications.",
                category="GOVERNANCE",
                priority=6.5,
                confidence=0.80,
                metadata={
                    'governance_score': governance_score,
                    'missing_metadata': ["Description des colonnes", "Propriétaires des données", "Classifications", "Règles de rétention"],
                    'governance_actions': ["Créer catalogue de données", "Documenter métadonnées", "Définir ownership", "Implémenter classifications"],
                    'color': 'blue',
                    'complexity_indicators': {
                        'columns': headers_count,
                        'rows': total_rows,
                        'entities_variety': len(detected_entities)
                    },
                    'source': 'smart_analysis'
                },
                created_at=datetime.now()
            )
            recommendations.append(rec)
    
    return recommendations


 def _process_file_by_chunks(self, file_id, job_id, filename, request):  
        """Traite le fichier CSV par chunks pour éviter les problèmes de mémoire"""  
          
        # Récupérer le fichier depuis GridFS  
        grid_file = fs.get(file_id)  
          
        # Lire par chunks de 1000 lignes  
        chunk_size = 1000  
        headers = None  
        detected_entities = set()  
        chunk_number = 0  
          
        # Initialiser les analyseurs (même logique qu'avant)  
        analyzer = create_enhanced_analyzer_engine("moroccan_entities_model_v2")  
        semantic_analyzer = SemanticAnalyzer("moroccan_entities_model_v2")  
        auto_tagger = IntelligentAutoTagger(analyzer, semantic_analyzer)  
          
        # Lire le fichier ligne par ligne  
        content = grid_file.read().decode('utf-8')  
        reader = csv.reader(io.StringIO(content))  
          
        # Traiter par chunks  
        current_chunk = []  
        for i, row in enumerate(reader):  
            if i == 0:  # Headers  
                headers = row  
                continue  
              
            current_chunk.append(row)  
              
            # Traiter le chunk quand il atteint la taille limite  
            if len(current_chunk) >= chunk_size:  
                entities = self._analyze_chunk(current_chunk, headers, auto_tagger, filename)  
                detected_entities.update(entities)  
                  
                # Sauvegarder le chunk  
                self._save_chunk(job_id, chunk_number, headers, current_chunk)  
                  
                current_chunk = []  
                chunk_number += 1  
          
        # Traiter le dernier chunk  
        if current_chunk:  
            entities = self._analyze_chunk(current_chunk, headers, auto_tagger, filename)  
            detected_entities.update(entities)  
            self._save_chunk(job_id, chunk_number, headers, current_chunk)  
          
        # Générer les recommandations IA (préserver la fonctionnalité existante)  
        recommendations = []  
        try:  
            gemini_api_key = os.getenv('GEMINI_API_KEY')  
              
            import asyncio  
            async def generate_recommendations_async():  
                async with GeminiClient(gemini_api_key) as gemini_client:  
                    recommendation_engine = IntelligentRecommendationEngine(gemini_client, gemini_api_key)  
                      
                    # Créer le profil du dataset avec les données par chunks  
                    sample_data = self._get_sample_data_from_chunks(job_id, headers)  
                    dataset_profile = recommendation_engine.create_dataset_profile_from_presidio(  
                        str(job_id), detected_entities, headers, sample_data  
                    )  
                      
                    comprehensive_recommendations = await recommendation_engine.generate_comprehensive_recommendations(dataset_profile)  
                    return comprehensive_recommendations  
              
            comprehensive_recommendations = asyncio.run(generate_recommendations_async())  
            recommendations = comprehensive_recommendations.recommendations  
              
            # Stocker l'ID du job pour les recommandations  
            request.session['current_job_id'] = str(job_id)  
              
        except Exception as e:  
            print(f"Erreur lors de la génération des recommandations: {e}")  
            recommendations = []  
          
        # Retour identique à l'original  
        return render(request, 'csv_anonymizer/select_entities.html', {  
            'job_id': str(job_id),  
            'detected_entities': list(detected_entities),  
            'headers': headers,  
            'has_recommendations': len(recommendations) > 0  
        })  
  
 def _analyze_chunk(self, chunk_data, headers, auto_tagger, filename):  
        """Analyse un chunk de données"""  
        detected_entities = set()  
          
        for row in chunk_data:  
            for i, value in enumerate(row):  
                if isinstance(value, str) and i < len(headers):  
                    entities, tags = auto_tagger.analyze_and_tag(value, dataset_name=filename)  
                    for entity in entities:  
                        if entity.entity_type not in EXCLUDED_ENTITY_TYPES:  
                            detected_entities.add(entity.entity_type)  
          
        return detected_entities  
  
 def _save_chunk(self, job_id, chunk_number, headers, chunk_data):  
        """Sauvegarde un chunk dans MongoDB"""  
        chunk_doc = {  
            'job_id': str(job_id),  
            'chunk_number': chunk_number,  
            'headers': headers,  
            'data': [dict(zip(headers, row)) for row in chunk_data],  
            'created_at': datetime.datetime.now()  
        }  
        csv_db['csv_chunks'].insert_one(chunk_doc)  
  
 def _get_sample_data_from_chunks(self, job_id, headers):  
        """Récupère un échantillon de données depuis les chunks pour les recommandations IA"""  
        # Prendre les 10 premières lignes du premier chunk pour l'analyse IA  
        first_chunk = csv_db['csv_chunks'].find_one({'job_id': str(job_id), 'chunk_number': 0})  
        if first_chunk and first_chunk['data']:  
            return first_chunk['data'][:10]  # Limiter à 10 lignes comme dans l'original  
        return []

class DownloadCleanedFileView(View):
    def get(self, request, job_id):
        """Télécharge le fichier nettoyé"""
        if not request.session.get("user_email"):
            return JsonResponse({'error': 'Non autorisé'}, status=401)
        
        # Récupérer les chunks nettoyés
        chunks = list(csv_db['csv_chunks'].find({'job_id': str(job_id)}).sort('chunk_number', 1))
        if not chunks:
            return JsonResponse({'error': 'Données non trouvées'}, status=404)
        
        headers = chunks[0]['headers']
        all_data = []
        for chunk in chunks:
            all_data.extend(chunk['data'])
        
        # Générer le CSV
        df = pd.DataFrame(all_data)
        output = io.StringIO()
        df.to_csv(output, index=False)
        
        # Récupérer le nom original
        job = main_db.anonymization_jobs.find_one({'_id': ObjectId(job_id)})
        original_filename = job['original_filename'] if job else 'file.csv'
        
        # Créer la réponse HTTP
        csv_content = output.getvalue()
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="cleaned_{original_filename}"'
        
        return response

import re

class ProcessCSVView(View):  
    def post(self, request, job_id):  
        # Vérifications d'authentification existantes  
        if not request.session.get("user_email"):  
            return redirect('login_form')  
          
        user_email = request.session.get("user_email")  
        user = users.find_one({'email': user_email})  
          
        if user and user.get('role') != 'admin':  
            return redirect('authapp:home')  
          
        # Convertir le string job_id en ObjectId MongoDB  
        try:  
            if len(job_id) == 24:  
                object_id = ObjectId(job_id)  
            else:  
                object_id = job_id  
        except:  
            return JsonResponse({'error': 'ID invalide'}, status=400)  
          
        # Récupérer les entités sélectionnées  
        selected_entities = request.POST.getlist('entities')  
        
        print(f"=== DÉBUT ANONYMISATION ULTRA-RAPIDE (VECTORISATION) ===")
        print(f"Job ID: {job_id}")
        print(f"Entités sélectionnées: {selected_entities}")
        
        # 1. Récupérer tous les chunks
        chunks = list(csv_db['csv_chunks'].find({'job_id': str(object_id)}).sort('chunk_number', 1))
        if not chunks:  
            return JsonResponse({'error': 'Données non trouvées'}, status=404)  
          
        headers = chunks[0]['headers']  
        
        # 2. Combiner toutes les données
        print("Chargement des données...")
        all_data = []  
        for chunk in chunks:  
            all_data.extend(chunk['data'])  
        
        df = pd.DataFrame(all_data)
        print(f"Dataset: {len(df)} lignes, {len(df.columns)} colonnes")
        
        # 3. MASQUAGE ULTRA-RAPIDE PAR REGEX VECTORISÉ (sans multiprocessing)
        # Patterns regex optimisés
        patterns = {
            'EMAIL_ADDRESS': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'PHONE_NUMBER': r'\b(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b',
            'IBAN_CODE': r'\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b',
            'CREDIT_CARD': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
            'ID_MAROC': r'\b[A-Z]{1,2}\d{5,8}\b',
            'IP_ADDRESS': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'URL': r'https?://[^\s]+',
        }
        
        # Masques de remplacement
        replacements = {
            'EMAIL_ADDRESS': '[EMAIL_MASQUÉ]',
            'PHONE_NUMBER': '[TÉLÉPHONE_MASQUÉ]',
            'IBAN_CODE': '[IBAN_MASQUÉ]',
            'CREDIT_CARD': '[CARTE_MASQUÉE]',
            'ID_MAROC': '[CIN_MASQUÉE]',
            'IP_ADDRESS': '[IP_MASQUÉE]',
            'URL': '[URL_MASQUÉE]',
            'PERSON': '[NOM_MASQUÉ]',
            'LOCATION': '[LIEU_MASQUÉ]',
            'DATE_TIME': '[DATE_MASQUÉE]',
        }
        
        # Identifier les colonnes à traiter intelligemment
        columns_to_process = self._identify_columns_to_mask(df, selected_entities, headers)
        
        print(f"Colonnes à anonymiser: {list(columns_to_process.keys())}")
        print("Début masquage vectorisé...")
        
        # 4. TRAITEMENT VECTORISÉ (ULTRA-RAPIDE)
        output_df = df.copy()
        
        for column, entity_types in columns_to_process.items():
            if column not in output_df.columns:
                continue
            
            print(f"Masquage '{column}' ({len(entity_types)} types)...")
            
            # Convertir en string pour traitement
            col_series = output_df[column].astype(str)
            
            # Appliquer les masques pour chaque type d'entité
            for entity_type in entity_types:
                if entity_type in patterns:
                    # REGEX VECTORISÉ avec pandas (TRÈS RAPIDE)
                    pattern = patterns[entity_type]
                    mask = replacements[entity_type]
                    col_series = col_series.str.replace(pattern, mask, regex=True)
                    
                elif entity_type in ['PERSON', 'LOCATION', 'DATE_TIME']:
                    # Masquage simple vectorisé
                    mask = replacements[entity_type]
                    # Remplacer seulement les valeurs non-vides
                    col_series = col_series.apply(
                        lambda x: mask if x and str(x).strip() and str(x) != 'nan' else x
                    )
            
            output_df[column] = col_series
        
        print("✅ Anonymisation terminée")
        
        # 5. Mettre à jour le statut du job
        main_db.anonymization_jobs.update_one(  
            {'_id': object_id},  
            {'$set': {'status': 'completed'}}  
        )  
        
        # 6. Générer le CSV optimisé
        print("Génération du fichier CSV...")
        output = io.StringIO()  
        output_df.to_csv(output, index=False)
        
        job = main_db.anonymization_jobs.find_one({'_id': object_id})
        original_filename = job['original_filename'] if job else 'file.csv'
        
        # 7. Créer la réponse HTTP
        csv_content = output.getvalue()
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')  
        response['Content-Disposition'] = f'attachment; filename="anonymized_{original_filename}"'
        
        print(f"=== FIN ANONYMISATION - Fichier prêt ({len(csv_content)} bytes) ===")
        
        return response
    
    def _identify_columns_to_mask(self, df, selected_entities, headers):
        """
        Identifie intelligemment les colonnes à masquer basé sur :
        1. Les noms de colonnes (ultra-rapide)
        2. Un échantillonnage rapide si nécessaire
        """
        columns_to_process = {}
        
        # Mots-clés pour identifier les colonnes rapidement
        keywords_map = {
            'EMAIL_ADDRESS': ['email', 'mail', 'e-mail', 'courriel'],
            'PHONE_NUMBER': ['phone', 'tel', 'telephone', 'mobile', 'gsm', 'portable'],
            'PERSON': ['nom', 'prenom', 'name', 'firstname', 'lastname', 'prénom', 'client', 'user'],
            'IBAN_CODE': ['iban', 'compte', 'account', 'rib', 'bank'],
            'CREDIT_CARD': ['carte', 'card', 'cb', 'credit', 'visa', 'mastercard'],
            'ID_MAROC': ['cin', 'id', 'identité', 'identity', 'cni'],
            'LOCATION': ['ville', 'city', 'adresse', 'address', 'lieu', 'location', 'pays', 'country'],
            'DATE_TIME': ['date', 'time', 'datetime', 'heure', 'timestamp', 'created', 'updated'],
            'IP_ADDRESS': ['ip', 'adresse_ip', 'ip_address'],
            'URL': ['url', 'site', 'website', 'lien', 'link'],
        }
        
        # Méthode 1 : Identification par nom de colonne (99% des cas)
        for entity_type in selected_entities:
            if entity_type in keywords_map:
                keywords = keywords_map[entity_type]
                
                # Chercher les colonnes correspondantes
                for col in headers:
                    col_lower = col.lower()
                    if any(kw in col_lower for kw in keywords):
                        if col not in columns_to_process:
                            columns_to_process[col] = set()
                        columns_to_process[col].add(entity_type)
                        print(f"✓ Colonne '{col}' identifiée pour {entity_type}")
        
        # Méthode 2 : Si aucune colonne trouvée par nom, échantillonner SEULEMENT 3 lignes
        if not columns_to_process:
            print("⚠️ Aucune colonne identifiée par nom - échantillonnage minimal (3 lignes)...")
            
            # Prendre seulement 3 lignes aléatoires pour test
            sample_df = df.sample(n=min(3, len(df)))
            
            for col in df.columns:
                if col not in columns_to_process:
                    sample_values = sample_df[col].dropna().astype(str).tolist()
                    
                    for entity_type in selected_entities:
                        if self._quick_check_entity(sample_values, entity_type):
                            if col not in columns_to_process:
                                columns_to_process[col] = set()
                            columns_to_process[col].add(entity_type)
                            print(f"✓ Colonne '{col}' détectée par échantillon pour {entity_type}")
        
        # Méthode 3 : Si toujours rien, appliquer sur TOUTES les colonnes texte (sécurité)
        if not columns_to_process:
            print("⚠️ Mode sécurité : application sur toutes colonnes texte")
            for col in df.select_dtypes(include=['object']).columns:
                columns_to_process[col] = set(selected_entities)
        
        return columns_to_process
    
    def _quick_check_entity(self, sample_values, entity_type):
        """Vérification rapide si un type d'entité est présent dans l'échantillon"""
        if not sample_values:
            return False
        
        # Patterns de détection rapide
        quick_patterns = {
            'EMAIL_ADDRESS': r'@',
            'PHONE_NUMBER': r'\d{4,}',
            'IBAN_CODE': r'[A-Z]{2}\d{2}',
            'CREDIT_CARD': r'\d{4}.*\d{4}',
            'IP_ADDRESS': r'\d+\.\d+\.\d+\.\d+',
            'URL': r'https?://',
        }
        
        if entity_type in quick_patterns:
            pattern = quick_patterns[entity_type]
            for val in sample_values:
                if re.search(pattern, str(val)):
                    return True
        
        # Pour PERSON, LOCATION, DATE_TIME : toujours retourner False
        # car ils seront détectés par nom de colonne
        return False

class StatisticsView(View):      
    def get(self, request):      
        if not request.session.get("user_email"):      
            return redirect('login_form')      
              
        user_email = request.session.get("user_email")      
              
        # Vérifier le rôle de l'utilisateur      
        user = users.find_one({'email': user_email})      
      
        if user and user.get('role') != 'admin':      
            return redirect('authapp:home')     
                
        # Récupérer tous les jobs complétés de l'utilisateur      
        completed_jobs = list(main_db.anonymization_jobs.find({      
            'user_email': user_email,      
            'status': 'completed'      
        }))      
              
        total_files = len(completed_jobs)      
        entity_stats = {}      
        total_entities_detected = 0      
              
        # Utiliser les données anonymisées au lieu des données temporaires    
        anonymized_collection = csv_db['anonymized_files']    
          
        # Initialiser le système sémantique pour les statistiques  
        analyzer = create_enhanced_analyzer_engine("moroccan_entities_model_v2")  
        semantic_analyzer = SemanticAnalyzer("moroccan_entities_model_v2")  
        auto_tagger = IntelligentAutoTagger(analyzer, semantic_analyzer)  
            
        for job in completed_jobs:      
            job_id = str(job['_id'])      
                  
            # Chercher dans anonymized_files au lieu de csv_data    
            #anonymized_record = anonymized_collection.find_one({'job_id': job_id})      
                  
            #if anonymized_record:      
                # Utiliser les données anonymisées pour les statistiques    
                #csv_data = anonymized_record['anonymized_data']    

            chunks = list(csv_db['csv_chunks'].find({'job_id': job_id}).sort('chunk_number', 1))  
            if chunks:  
                csv_data = []  
                for chunk in chunks:  
                    csv_data.extend(chunk['data'])  
                      
                for row in csv_data:      
                    for header, value in row.items():      
                        if isinstance(value, str) and value.strip():  
                            job_record = main_db.anonymization_jobs.find_one({'_id': ObjectId(job_id)})  
    
                            filename = job_record['original_filename'] if job_record else 'unknown'  
                            entities, tags = auto_tagger.analyze_and_tag(value, dataset_name=filename)
                              
                            for entity in entities:  
                                entity_type = entity.entity_type  
                                # Exclure les entités indésirables des statistiques    
                                if entity_type not in EXCLUDED_ENTITY_TYPES:    
                                    if entity_type in entity_stats:      
                                        entity_stats[entity_type] += 1      
                                    else:      
                                        entity_stats[entity_type] = 1      
                                    total_entities_detected += 1      
              
        # Calculer les niveaux de risque basés sur les types d'entités détectées      
        risk_levels = self.calculate_risk_levels(entity_stats, total_entities_detected)      
              
        context = {      
            'total_files': total_files,      
            'entity_stats': entity_stats,      
            'risk_levels': risk_levels,      
        }      
              
        return render(request, 'csv_anonymizer/statistics.html', context)      
          
    def calculate_risk_levels(self, entity_stats, total_entities):      
        """Calculer les pourcentages de niveaux de risque"""      
        if total_entities == 0:      
            return {      
                'critique': 0,      
                'élevé': 0,      
                'moyen': 0,      
                'faible': 0      
            }      
              
        # Définir les niveaux de risque par type d'entité      
        high_risk_entities = ['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'CREDIT_CARD', 'IBAN_CODE', 'ID_MAROC']
        medium_risk_entities = ['DATE_TIME', 'LOCATION', 'IP_ADDRESS']      
              
        critique_count = 0      
        eleve_count = 0      
        moyen_count = 0      
        faible_count = 0      
              
        for entity_type, count in entity_stats.items():      
            if entity_type in high_risk_entities:      
                critique_count += count      
            elif entity_type in medium_risk_entities:      
                eleve_count += count      
            else:      
                moyen_count += count      
              
        # Calculer les pourcentages      
        critique_percent = round((critique_count / total_entities) * 100, 1)      
        eleve_percent = round((eleve_count / total_entities) * 100, 1)      
        moyen_percent = round((moyen_count / total_entities) * 100, 1)      
        faible_percent = round(100 - critique_percent - eleve_percent - moyen_percent, 1)      
              
        return {      
            'critique': critique_percent,      
            'élevé': eleve_percent,      
            'moyen': moyen_percent,      
            'faible': max(0, faible_percent)  # S'assurer que ce n'est pas négatif      
        }
    


class RemoveDuplicatesView(View):  
    def post(self, request):  
        if not request.session.get("user_email"):  
            return JsonResponse({'error': 'Non autorisé'}, status=401)  
          
        user_email = request.session.get("user_email")  
        user = users.find_one({'email': user_email})  
          
        if user and user.get('role') != 'admin':  
            return JsonResponse({'error': 'Accès refusé'}, status=403)  
          
        try:  
         data = json.loads(request.body)  
         job_id = data.get('job_id')  
          
         if not job_id:  
            return JsonResponse({'error': 'job_id manquant'}, status=400)  
          
        # 1. Lire tous les chunks du job  
         chunks = list(csv_db['csv_chunks'].find({'job_id': str(job_id)}).sort('chunk_number', 1))  
         if not chunks:  
            return JsonResponse({'error': 'Données non trouvées'}, status=404)  
          
        # 2. Combiner toutes les données  
         all_data = []  
         headers = chunks[0]['headers']  
         for chunk in chunks:  
            all_data.extend(chunk['data'])  
          
        # 3. Supprimer les doublons  
         df = pd.DataFrame(all_data)  
         original_count = len(df)  
         df_cleaned = df.drop_duplicates()  
          
        # 4. Re-sauvegarder en chunks  
         self._save_cleaned_data_as_chunks(job_id, headers, df_cleaned.to_dict('records'))  
          
         return JsonResponse({  
            'success': True,  
            'message': f'{original_count - len(df_cleaned)} doublons supprimés',  
            'rows_removed': original_count - len(df_cleaned)  
         })  
      
        except Exception as e:  
         return JsonResponse({'error': str(e)}, status=500)  
  
    def _save_cleaned_data_as_chunks(self, job_id, headers, cleaned_data):  
     """Re-sauvegarde les données nettoyées en chunks"""  
     # Supprimer les anciens chunks  
     csv_db['csv_chunks'].delete_many({'job_id': str(job_id)})  
      
    # Re-créer les chunks avec les données nettoyées  
     chunk_size = 1000  
     for i in range(0, len(cleaned_data), chunk_size):  
        chunk_data = cleaned_data[i:i + chunk_size]  
        chunk_doc = {  
            'job_id': str(job_id),  
            'chunk_number': i // chunk_size,  
            'headers': headers,  
            'data': chunk_data,  
            'created_at': datetime.datetime.now()  
        }  
        csv_db['csv_chunks'].insert_one(chunk_doc)

class RemoveMissingValuesView(View):  
    def post(self, request):  
        if not request.session.get("user_email"):  
            return JsonResponse({'error': 'Non autorisé'}, status=401)  
          
        user_email = request.session.get("user_email")  
        user = users.find_one({'email': user_email})  
          
        if user and user.get('role') != 'admin':  
            return JsonResponse({'error': 'Accès refusé'}, status=403)  
          
        try:  
         data = json.loads(request.body)  
         job_id = data.get('job_id')  
          
         if not job_id:  
            return JsonResponse({'error': 'job_id manquant'}, status=400)  
          
        # Lire depuis les chunks  
         chunks = list(csv_db['csv_chunks'].find({'job_id': str(job_id)}).sort('chunk_number', 1))  
         if not chunks:  
            return JsonResponse({'error': 'Données non trouvées'}, status=404)  
          
        # Combiner et nettoyer  
         all_data = []  
         headers = chunks[0]['headers']  
         for chunk in chunks:  
            all_data.extend(chunk['data'])  
          
         df = pd.DataFrame(all_data)  
         original_count = len(df)  
         df_cleaned = df.dropna()  
          
        # Re-sauvegarder en chunks  
         self._save_cleaned_data_as_chunks(job_id, headers, df_cleaned.to_dict('records'))  
          
         return JsonResponse({  
            'success': True,  
            'message': f'{original_count - len(df_cleaned)} lignes avec valeurs manquantes supprimées',  
            'rows_removed': original_count - len(df_cleaned)  
         })  
      
        except Exception as e:  
         return JsonResponse({'error': str(e)}, status=500)

class DataStewardDashboardView(View):  
    def get(self, request):  
        if not request.session.get("user_email"):  
            return redirect('login_form')  
          
        user_email = request.session.get("user_email")  
        user = users.find_one({'email': user_email})  
          
        # Vérifier que c'est un data steward  
        if not user or user.get('role') != 'user':  
            return redirect('authapp:home')  
          
        # Récupérer les jobs récents de l'utilisateur  
        recent_jobs = list(main_db.anonymization_jobs.find({  
            'user_email': user_email,  
            'status': 'completed'  
        }).sort('upload_date', -1).limit(10))  
          
        return render(request, 'csv_anonymizer/datasteward_dashboard.html', {  
            'recent_jobs': recent_jobs,  
            'user': user  
        })