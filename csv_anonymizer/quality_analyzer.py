"""
Analyseur de qualité des données pour détecter :
- Valeurs nulles/manquantes (None, '', 'None', NaN)
- Doublons complets
- Incohérences de format (emails, téléphones, dates, IDs)

Usage:
    from quality_analyzer import DataQualityAnalyzer
    
    analyzer = DataQualityAnalyzer()
    report = analyzer.analyze_full_dataset(headers, all_data)
"""

import pandas as pd
import re
from datetime import datetime

class DataQualityAnalyzer:
    """Analyseur de qualité des données CSV"""
    
    def __init__(self):
        self.quality_report = {}
    
    def analyze_full_dataset(self, headers, all_data):
        """
        Analyse complète du dataset
        
        Args:
            headers: Liste des noms de colonnes
            all_data: Liste de dictionnaires (lignes)
        
        Returns:
            dict: Rapport de qualité détaillé avec:
                - total_rows, total_columns
                - missing_values: {total_missing, missing_percentage, columns_with_missing}
                - duplicates: {total_duplicates, duplicate_percentage, duplicate_groups}
                - inconsistencies: {total_inconsistencies, columns_with_issues}
                - quality_score: float (0-10)
                - critical_issues: liste
        """
        print(f"🔍 Analyse qualité: {len(all_data)} lignes, {len(headers)} colonnes")
        
        # Convertir en DataFrame pour faciliter l'analyse
        df = pd.DataFrame(all_data)
        
        report = {
            'total_rows': len(df),
            'total_columns': len(headers),
            'analysis_date': datetime.now().isoformat(),
            'missing_values': self._analyze_missing_values(df, headers),
            'duplicates': self._analyze_duplicates(df),
            'inconsistencies': self._analyze_inconsistencies(df, headers),
            'data_types': self._analyze_data_types(df, headers),
            'quality_score': 0.0,  # Calculé à la fin
            'critical_issues': []
        }
        
        # Calculer le score de qualité global
        report['quality_score'] = self._calculate_quality_score(report)
        
        # Identifier les problèmes critiques
        report['critical_issues'] = self._identify_critical_issues(report)
        
        print(f"✅ Analyse terminée - Score qualité: {report['quality_score']:.1f}/10")
        print(f"⚠️ Problèmes critiques: {len(report['critical_issues'])}")
        
        return report
    
    def _analyze_missing_values(self, df, headers):
        """Détecte les valeurs manquantes par colonne"""
        missing_report = {
            'total_missing': 0,
            'missing_percentage': 0.0,
            'columns_with_missing': {}
        }
        
        for col in headers:
            if col not in df.columns:
                continue
            
            # Compter TOUS les types de valeurs manquantes
            col_series = df[col].astype(str)
            
            # 1. Valeurs NULL/NaN pandas
            null_count = df[col].isna().sum()
            
            # 2. Chaînes vides (après strip)
            empty_count = (col_series.str.strip() == '').sum()
            
            # 3. Chaîne "None" (insensible à la casse)
            none_count = (col_series.str.lower().str.strip() == 'none').sum()
            
            # 4. Chaîne "nan" (insensible à la casse)
            nan_str_count = (col_series.str.lower().str.strip() == 'nan').sum()
            
            # Total en évitant les doublons
            total_missing = len(df[(df[col].isna()) | 
                                  (col_series.str.strip() == '') | 
                                  (col_series.str.lower().str.strip() == 'none') |
                                  (col_series.str.lower().str.strip() == 'nan')])
            
            if total_missing > 0:
                missing_pct = (total_missing / len(df)) * 100
                missing_report['columns_with_missing'][col] = {
                    'count': int(total_missing),
                    'percentage': round(missing_pct, 2),
                    'null_count': int(null_count),
                    'empty_count': int(empty_count),
                    'none_count': int(none_count),
                    'nan_str_count': int(nan_str_count)
                }
                missing_report['total_missing'] += total_missing
        
        # Calcul du pourcentage global
        total_cells = len(df) * len(headers)
        if total_cells > 0:
            missing_report['missing_percentage'] = round(
                (missing_report['total_missing'] / total_cells) * 100, 2
            )
        
        print(f"📊 Valeurs manquantes: {missing_report['total_missing']} ({missing_report['missing_percentage']}%)")
        
        return missing_report
    
    def _analyze_duplicates(self, df):
        """Détecte les lignes dupliquées COMPLÈTES"""
        duplicate_report = {
            'total_duplicates': 0,
            'duplicate_percentage': 0.0,
            'duplicate_groups': []
        }
        
        # Trouver les doublons complets (toutes colonnes identiques)
        duplicated_mask = df.duplicated(keep=False)
        duplicate_count = duplicated_mask.sum()
        
        if duplicate_count > 0:
            duplicate_report['total_duplicates'] = int(duplicate_count)
            duplicate_report['duplicate_percentage'] = round(
                (duplicate_count / len(df)) * 100, 2
            )
            
            # Identifier les groupes de doublons (limiter à 5 exemples)
            duplicate_df = df[duplicated_mask]
            duplicate_groups = duplicate_df.groupby(list(df.columns), dropna=False).size()
            
            for idx, (group, count) in enumerate(duplicate_groups.head(5).items()):
                if count > 1:  # Seulement les vrais doublons
                    if isinstance(group, tuple):
                        group_dict = dict(zip(df.columns, group))
                    else:
                        group_dict = {df.columns[0]: group}
                    
                    duplicate_report['duplicate_groups'].append({
                        'example': group_dict,
                        'occurrences': int(count)
                    })
        
        print(f"🔁 Doublons: {duplicate_report['total_duplicates']} lignes ({duplicate_report['duplicate_percentage']}%)")
        
        return duplicate_report
    
    def _analyze_inconsistencies(self, df, headers):
        """Détecte les incohérences de format"""
        inconsistency_report = {
            'total_inconsistencies': 0,
            'columns_with_issues': {}
        }
        
        for col in headers:
            if col not in df.columns:
                continue
            
            column_issues = []
            
            # Vérifier les colonnes qui semblent contenir des emails
            if any(keyword in col.lower() for keyword in ['email', 'mail', 'courriel']):
                invalid_emails = self._check_email_format(df[col])
                if invalid_emails > 0:
                    column_issues.append({
                        'type': 'invalid_email_format',
                        'count': invalid_emails,
                        'description': f'{invalid_emails} emails invalides détectés'
                    })
            
            # Vérifier les colonnes de téléphone
            if any(keyword in col.lower() for keyword in ['phone', 'tel', 'telephone', 'mobile']):
                invalid_phones = self._check_phone_format(df[col])
                if invalid_phones > 0:
                    column_issues.append({
                        'type': 'invalid_phone_format',
                        'count': invalid_phones,
                        'description': f'{invalid_phones} numéros invalides'
                    })
            
            # Vérifier les colonnes de dates
            if any(keyword in col.lower() for keyword in ['date', 'time', 'datetime']):
                invalid_dates = self._check_date_format(df[col])
                if invalid_dates > 0:
                    column_issues.append({
                        'type': 'invalid_date_format',
                        'count': invalid_dates,
                        'description': f'{invalid_dates} dates invalides'
                    })
            
            # Vérifier les colonnes ID/CIN
            if any(keyword in col.lower() for keyword in ['id', 'cin', 'carte']):
                invalid_ids = self._check_id_format(df[col])
                if invalid_ids > 0:
                    column_issues.append({
                        'type': 'invalid_id_format',
                        'count': invalid_ids,
                        'description': f'{invalid_ids} identifiants invalides'
                    })
            
            if column_issues:
                inconsistency_report['columns_with_issues'][col] = column_issues
                inconsistency_report['total_inconsistencies'] += sum(
                    issue['count'] for issue in column_issues
                )
        
        print(f"⚠️ Incohérences: {inconsistency_report['total_inconsistencies']} problèmes détectés")
        
        return inconsistency_report
    
    def _check_email_format(self, series):
        """Vérifie le format des emails"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        # Compter les emails invalides (non-vides qui ne matchent pas le pattern)
        non_empty = series.dropna().astype(str)
        non_empty = non_empty[non_empty.str.strip() != '']
        non_empty = non_empty[non_empty.str.lower() != 'none']
        
        if len(non_empty) == 0:
            return 0
        
        invalid_count = (~non_empty.str.match(email_pattern)).sum()
        return int(invalid_count)
    
    def _check_phone_format(self, series):
        """Vérifie le format des numéros de téléphone"""
        # Pattern flexible pour téléphones marocains
        phone_pattern = r'^(\+212|0)[5-7][0-9]{8}$|^[0-9\s\-\+\(\)]{8,15}'
        
        non_empty = series.dropna().astype(str)
        non_empty = non_empty[non_empty.str.strip() != '']
        non_empty = non_empty[non_empty.str.lower() != 'none']
        
        if len(non_empty) == 0:
            return 0
        
        # Nettoyer les espaces/tirets avant vérification
        cleaned = non_empty.str.replace(r'[\s\-\(\)]', '', regex=True)
        invalid_count = (~cleaned.str.match(phone_pattern)).sum()
        
        return int(invalid_count)
    
    def _check_date_format(self, series):
        """Vérifie le format des dates"""
        non_empty = series.dropna().astype(str)
        non_empty = non_empty[non_empty.str.strip() != '']
        non_empty = non_empty[non_empty.str.lower() != 'none']
        
        if len(non_empty) == 0:
            return 0
        
        invalid_count = 0
        for value in non_empty:
            try:
                # Essayer plusieurs formats de date
                pd.to_datetime(value, errors='raise')
            except:
                invalid_count += 1
        
        return invalid_count
    
    def _check_id_format(self, series):
        """Vérifie le format des identifiants (CIN marocain)"""
        # Format CIN marocain : 1-2 lettres suivies de 5-8 chiffres
        id_pattern = r'^[A-Z]{1,2}\d{5,8}'
        
        non_empty = series.dropna().astype(str)
        non_empty = non_empty[non_empty.str.strip() != '']
        non_empty = non_empty[non_empty.str.lower() != 'none']
        
        if len(non_empty) == 0:
            return 0
        
        invalid_count = (~non_empty.str.match(id_pattern)).sum()
        return int(invalid_count)
    
    def _analyze_data_types(self, df, headers):
        """Analyse les types de données par colonne"""
        type_report = {}
        
        for col in headers:
            if col not in df.columns:
                continue
            
            # Déterminer le type dominant
            non_null = df[col].dropna()
            
            if len(non_null) == 0:
                type_report[col] = 'empty'
                continue
            
            # Tenter de détecter le type
            numeric_count = pd.to_numeric(non_null, errors='coerce').notna().sum()
            datetime_count = pd.to_datetime(non_null, errors='coerce').notna().sum()
            
            if numeric_count / len(non_null) > 0.8:
                type_report[col] = 'numeric'
            elif datetime_count / len(non_null) > 0.8:
                type_report[col] = 'datetime'
            else:
                type_report[col] = 'string'
        
        return type_report
    
    def _calculate_quality_score(self, report):
        """Calcule un score de qualité global (0-10)"""
        score = 10.0
        
        # Pénalités pour valeurs manquantes
        missing_pct = report['missing_values']['missing_percentage']
        score -= min(3.0, missing_pct / 5)  # Max -3 points
        
        # Pénalités pour doublons
        duplicate_pct = report['duplicates']['duplicate_percentage']
        score -= min(2.0, duplicate_pct / 5)  # Max -2 points
        
        # Pénalités pour incohérences
        inconsistency_count = report['inconsistencies']['total_inconsistencies']
        total_cells = report['total_rows'] * report['total_columns']
        if total_cells > 0:
            inconsistency_pct = (inconsistency_count / total_cells) * 100
            score -= min(3.0, inconsistency_pct / 3)  # Max -3 points
        
        return max(0.0, round(score, 1))
    
    def _identify_critical_issues(self, report):
        """Identifie les problèmes critiques nécessitant une action immédiate"""
        critical = []
        
        # Valeurs manquantes > 20%
        if report['missing_values']['missing_percentage'] > 20:
            critical.append({
                'severity': 'HIGH',
                'type': 'missing_values',
                'message': f"Taux élevé de valeurs manquantes: {report['missing_values']['missing_percentage']}%",
                'action': "Nettoyer ou compléter les données manquantes"
            })
        
        # Doublons > 10%
        if report['duplicates']['duplicate_percentage'] > 10:
            critical.append({
                'severity': 'HIGH',
                'type': 'duplicates',
                'message': f"Taux élevé de doublons: {report['duplicates']['duplicate_percentage']}%",
                'action': "Supprimer les lignes dupliquées"
            })
        
        # Incohérences importantes
        total_cells = report['total_rows'] * report['total_columns']
        if total_cells > 0:
            inconsistency_pct = (report['inconsistencies']['total_inconsistencies'] / total_cells) * 100
            if inconsistency_pct > 5:
                critical.append({
                    'severity': 'MEDIUM',
                    'type': 'inconsistencies',
                    'message': f"Incohérences de format détectées: {inconsistency_pct:.1f}%",
                    'action': "Standardiser les formats de données"
                })
        
        return critical


# Fonction utilitaire pour intégration rapide
def analyze_csv_quality(headers, all_data):
    """
    Fonction raccourci pour analyser la qualité d'un CSV
    
    Usage:
        quality_report = analyze_csv_quality(headers, all_data)
    
    Returns:
        dict: Rapport complet avec score, problèmes, recommandations
    """
    analyzer = DataQualityAnalyzer()
    return analyzer.analyze_full_dataset(headers, all_data)