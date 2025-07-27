from django.core.management.base import BaseCommand
from django.utils import timezone
from fraud_detection.models import RawTransaction, CustomUser
from fraud_detection.utils import apply_fraud_detection_model, generate_claude_analysis, update_client_statistics, update_bank_statistics
import random
from decimal import Decimal
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Génère des données d\'exemple réalistes pour la démonstration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=100,
            help='Nombre de transactions à générer'
        )

    def handle(self, *args, **options):
        count = options['count']
        
        # Récupérer ou créer un utilisateur admin
        admin_user = CustomUser.objects.filter(role='admin').first()
        if not admin_user:
            admin_user = CustomUser.objects.create_user(
                username='demo_admin',
                email='demo@example.com',
                password='demo123',
                role='admin',
                can_upload_data=True,
                can_run_analysis=True
            )

        self.stdout.write(f'Génération de {count} transactions réalistes...')

        # Données réalistes pour la génération
        transaction_types = ['TRF', 'RT', 'RCD', 'PF']
        status_choices = ['OK', 'KO', 'ATT']
        
        # Banques françaises réelles
        banks = [
            'BNP001', 'SG002', 'CA003', 'LCL004', 'BRED005',
            'CIC006', 'HSBC007', 'ING008', 'BOURSO009', 'HELLO010'
        ]
        
        # Noms de clients réalistes français
        prenoms = ['Jean', 'Marie', 'Pierre', 'Sophie', 'Michel', 'Catherine', 'Philippe', 'Nathalie', 'Alain', 'Isabelle',
                  'François', 'Sylvie', 'Patrick', 'Martine', 'Daniel', 'Christine', 'Bernard', 'Françoise', 'Laurent', 'Monique']
        noms = ['Martin', 'Bernard', 'Dubois', 'Thomas', 'Robert', 'Richard', 'Petit', 'Durand', 'Leroy', 'Moreau',
               'Simon', 'Laurent', 'Lefebvre', 'Michel', 'Garcia', 'David', 'Bertrand', 'Roux', 'Vincent', 'Fournier']
        
        # Générer des IDs clients avec noms réalistes
        clients = []
        for i in range(1, 301):
            prenom = random.choice(prenoms)
            nom = random.choice(noms)
            client_id = f'CLI{str(i).zfill(6)}'
            clients.append({
                'id': client_id,
                'nom': f'{prenom} {nom}',
                'type': random.choice(['particulier', 'entreprise', 'association'])
            })

        # Motifs de transaction réalistes
        motifs_trf = ['Virement salaire', 'Virement familial', 'Remboursement prêt', 'Paiement fournisseur', 'Transfert épargne']
        motifs_rt = ['Retrait DAB', 'Retrait guichet', 'Retrait étranger', 'Retrait urgence']
        motifs_rcd = ['Recharge carte', 'Recharge compte', 'Dépôt espèces', 'Virement entrant']
        motifs_pf = ['Facture EDF', 'Facture téléphone', 'Assurance auto', 'Loyer', 'Courses alimentaires', 'Essence', 'Restaurant']

        fraud_count = 0
        claude_analyses = 0

        for i in range(count):
            # Sélectionner des clients
            client_i_data = random.choice(clients)
            client_b_data = random.choice(clients)
            
            # Type de transaction avec probabilités réalistes
            trx_type = random.choices(
                transaction_types,
                weights=[40, 25, 20, 15],  # TRF plus fréquent
                k=1
            )[0]
            
            # Parfois faire des auto-transferts (épargne)
            if trx_type == 'TRF' and random.random() < 0.15:
                client_b_data = client_i_data

            # Générer un montant selon le type et avec distribution réaliste
            if trx_type == 'TRF':
                if random.random() < 0.6:  # 60% virements normaux
                    montant = Decimal(random.uniform(50, 3000))
                elif random.random() < 0.3:  # 30% virements moyens
                    montant = Decimal(random.uniform(3000, 15000))
                else:  # 10% gros virements
                    montant = Decimal(random.uniform(15000, 100000))
            elif trx_type == 'RT':
                if random.random() < 0.8:  # 80% retraits normaux
                    montant = Decimal(random.uniform(20, 500))
                else:  # 20% gros retraits
                    montant = Decimal(random.uniform(500, 3000))
            elif trx_type == 'RCD':
                montant = Decimal(random.uniform(10, 2000))
            else:  # PF
                montant = Decimal(random.uniform(5, 1500))

            # Générer une heure réaliste selon le type
            if trx_type == 'RT':
                # Retraits plus fréquents en journée
                if random.random() < 0.05:  # 5% la nuit (suspect)
                    hour = random.randint(2, 6)
                else:
                    hour = random.choices(
                        range(24),
                        weights=[1,1,1,1,1,1,2,4,6,8,10,12,12,10,8,6,4,3,2,2,2,1,1,1],
                        k=1
                    )[0]
            else:
                # Autres transactions plus étalées
                hour = random.randint(6, 23)
            
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            
            # Date aléatoire dans les 60 derniers jours avec plus de récentes
            if random.random() < 0.4:  # 40% dans les 7 derniers jours
                days_ago = random.randint(0, 7)
            elif random.random() < 0.3:  # 30% dans les 30 derniers jours
                days_ago = random.randint(8, 30)
            else:  # 30% dans les 60 derniers jours
                days_ago = random.randint(31, 60)
                
            transaction_date = timezone.now() - timedelta(days=days_ago)
            transaction_date = transaction_date.replace(hour=hour, minute=minute, second=second)

            # Sélectionner un motif selon le type
            if trx_type == 'TRF':
                motif = random.choice(motifs_trf)
            elif trx_type == 'RT':
                motif = random.choice(motifs_rt)
            elif trx_type == 'RCD':
                motif = random.choice(motifs_rcd)
            else:
                motif = random.choice(motifs_pf)

            # Statut avec probabilités réalistes
            etat = random.choices(
                status_choices,
                weights=[92, 6, 2],  # 92% OK, 6% KO, 2% ATT
                k=1
            )[0]

            transaction = RawTransaction.objects.create(
                trx=f'TXN{timezone.now().timestamp():.0f}{i:04d}',
                trx_time=transaction_date.strftime('%Y-%m-%d %H:%M:%S'),
                mls=int(transaction_date.timestamp() * 1000),
                trx_type=trx_type,
                montant=montant.quantize(Decimal('0.01')),
                client_i=client_i_data['id'],
                client_b=client_b_data['id'],
                bank_i=random.choice(banks),
                bank_b=random.choice(banks),
                etat=etat,
                uploaded_by=admin_user
            )

            # Appliquer le modèle ML avec logique plus sophistiquée
            ml_result = apply_fraud_detection_model(transaction)
            transaction.ml_is_fraud = ml_result['is_fraud']
            transaction.ml_feature_importance = ml_result['feature_importance']
            transaction.ml_processed_at = timezone.now()

            # Si fraude détectée → Analyse Claude plus détaillée
            if ml_result['is_fraud']:
                try:
                    claude_result = generate_claude_analysis(transaction, motif, client_i_data, client_b_data)
                    transaction.claude_explanation = claude_result['explanation']
                    transaction.claude_priority_level = claude_result['priority']
                    transaction.claude_analyzed_at = timezone.now()
                    claude_analyses += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'Erreur analyse Claude pour {transaction.trx}: {e}')
                    )
                
                fraud_count += 1

            transaction.save()

            # Mettre à jour les statistiques
            update_client_statistics(transaction.client_i)
            if transaction.client_i != transaction.client_b:
                update_client_statistics(transaction.client_b)
            update_bank_statistics(transaction.bank_i)
            if transaction.bank_i != transaction.bank_b:
                update_bank_statistics(transaction.bank_b)

            # Afficher le progrès
            if (i + 1) % 20 == 0:
                self.stdout.write(f'Généré {i + 1}/{count} transactions...')

        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Génération terminée!\n'
                f'- {count} transactions créées\n'
                f'- {fraud_count} fraudes détectées\n'
                f'- {claude_analyses} analyses Claude générées\n'
                f'- Données réalistes avec noms français et motifs authentiques'
            )
        )

