# Résultats expérimentaux et discussion

Ce chapitre présente les résultats de la campagne d'évaluation principale, réalisée avec la configuration gelée : encodeur WordLlama, générateur extractif hors-ligne, huit passages de contexte et seuil de suffisance de 0,55. Tous les chiffres proviennent des fichiers produits automatiquement par les scripts d'évaluation. Les intervalles entre crochets sont des intervalles de confiance à 95 %. Nous présentons successivement l'ingestion et le graphe, l'extraction, la recherche documentaire, les questions-réponses, les ablations, la recherche d'experts et les recommandations, avant une analyse d'erreurs, la discussion des hypothèses et l'examen des menaces à la validité.

## Ingestion et qualité du graphe

L'ingestion complète des 35 fichiers prend 18,5 secondes sur la machine de développement (quatre processeurs). La ré-exécution sans changement ne prend que 0,38 seconde : les 35 fichiers sont reconnus comme inchangés grâce à leur empreinte. Le traitement est dominé par l'OCR du document scanné, l'extraction des entités et relations et l'écriture dans Neo4j.

![Durée de l'ingestion complète par étape](../figures/fig_ingestion.png){width=15cm}

À l'issue de l'ingestion, 31 documents sont en vigueur et un est marqué comme remplacé ; deux documents sont écartés comme doublons (la copie exacte et la copie de travail) et le mémo piégé est en quarantaine. Le graphe compte 169 passages, 69 entités métier hors taxonomie et 153 relations extraites. Toutes ces relations portent au moins un document source et un passage justificatif. Leur confiance moyenne est de 0,77 ; 63 d'entre elles sont confirmées par au moins deux documents. Aucune entité n'est isolée, et le degré moyen d'une entité est de 5,1.

## Extraction des connaissances

| Mesure | Développement (D01–D20) | Test (D21–D35) |
|---|---|---|
| Relations : précision / rappel / F1 | 1,000 / 0,968 / 0,984 | 0,986 / 0,717 / 0,830 |
| Mentions d'entités : précision / rappel / F1 | 0,924 / 0,953 / 0,938 | 0,789 / 0,912 / 0,846 |

Table: Extraction de connaissances par règles

Sur les documents de développement, l'extraction est presque parfaite, ce qui n'a rien de surprenant : les règles ont été écrites en lisant ces documents. Le résultat significatif est celui des documents de test, jamais utilisés pour la mise au point. La précision reste très élevée (0,986) : quand une règle se déclenche, elle a presque toujours raison. Le rappel tombe en revanche à 0,717. L'écart se concentre sur deux types de relations : les dépendances entre applications (rappel 0,44 sur 16 relations) et les responsabilités (0,17 sur 12). Les documents de test, notamment la cartographie applicative et la cartographie des compétences, emploient des formulations et des mises en forme (tableaux, listes) que les règles n'avaient pas prévues.

Ce profil, très précis mais incomplet, est caractéristique des systèmes à base de règles. Il est préférable, dans un contexte bancaire, à l'inverse : une relation manquante se traduit par une réponse moins complète ou une abstention, alors qu'une relation fausse produit un fait erroné cité comme vérifié. C'est aussi l'argument principal en faveur d'un extracteur par LLM contraint et vérifié, qui pourrait combler les manques de rappel ; son apport n'a pas pu être mesuré faute de clé d'API.

La résolution d'entités réussit les 34 cas de son jeu de test, y compris les six variantes absentes du référentiel (fautes de frappe, formes abrégées) et les six cas négatifs pour lesquels aucune entité ne devait être reconnue. Ce score parfait doit être relativisé : le jeu est petit et a été construit par l'auteure du résolveur.

## Recherche documentaire

### Comparaison des stratégies

Le tableau suivant compare les six stratégies de récupération sur les 55 questions qui ont des documents de référence.

| Stratégie | Recall@5 | MRR | nDCG@5 | Couverture des preuves | Latence p50 (ms) |
|---|---|---|---|---|---|
| Vectoriel | 0,751 | 0,836 | 0,720 [0,65 ; 0,79] | 0,811 | 8,6 |
| BM25 | 0,874 | 0,888 | 0,831 [0,77 ; 0,88] | 0,849 | 6,9 |
| Hybride (BM25 et vecteurs) | 0,852 | 0,874 | 0,803 [0,74 ; 0,86] | 0,868 | 11,4 |
| Graphe seul | 0,810 | 0,760 | 0,708 [0,63 ; 0,78] | 0,651 | 17,9 |
| Hybride avec graphe (fixe) | 0,854 | 0,875 | 0,813 [0,75 ; 0,87] | 0,934 | 27,9 |
| Hybride final (routé) | 0,855 | 0,908 | 0,839 [0,78 ; 0,90] | 0,943 | 33,9 |

Table: Recherche documentaire par stratégie (55 questions)

Trois constats se dégagent. Le premier est la force de BM25 : la recherche lexicale seule obtient le meilleur rappel et un nDCG@5 de 0,831, très proche de l'architecture finale. Ce résultat rejoint celui de Thakur et al. (2021) : sur un vocabulaire spécialisé, fait de codes, de sigles et de noms d'applications, la correspondance exacte des termes est un signal très fort. Le deuxième est que l'architecture finale obtient le meilleur nDCG@5 (0,839) et surtout le meilleur MRR (0,908) et la meilleure couverture des preuves (0,943) : c'est elle qui place le plus souvent un document pertinent en tête et qui réunit le plus d'éléments de preuve dans le contexte. Le troisième est que les écarts entre les meilleures stratégies sont faibles au regard de l'incertitude. Comparée au RAG hybride, l'architecture finale gagne 0,035 point de nDCG@5, avec un intervalle de confiance [−0,01 ; 0,08] qui contient zéro (test des signes : p = 0,17). Comparée au RAG vectoriel, en revanche, le gain de 0,118 [0,07 ; 0,17] est net (31 questions gagnées, 3 perdues, p < 0,001).

Le coût du graphe est visible dans la latence : l'architecture finale met environ 34 millisecondes en valeur médiane pour la récupération, contre 7 pour BM25. Ce coût reste négligeable à l'échelle d'une question posée par un utilisateur.

### Effet de l'encodeur

L'ablation de l'encodeur éclaire le rôle de la composante vectorielle.

![Recherche documentaire : effet de l'encodeur sur chaque stratégie](../figures/fig_recherche_encodeurs.png){width=15cm}

Avec les vecteurs de mots moyennés de spaCy, la recherche vectorielle ne dépasse pas 0,409 de nDCG@5. Elle dégrade alors toutes les fusions : le RAG hybride tombe à 0,680, en dessous de BM25 seul, et l'architecture finale à 0,766. Avec WordLlama, la recherche vectorielle remonte à 0,720 et l'hybride dépasse 0,80. L'intérêt d'une recherche hybride dépend donc directement de la qualité de l'encodeur : avec un encodeur faible, ajouter un signal vectoriel nuit plus qu'il n'aide. Ce résultat incite à la prudence : nos conclusions sur la recherche vectorielle valent pour des encodeurs légers utilisables hors-ligne, et devraient être réévaluées avec un encodeur de phrases multilingue de meilleure qualité.

### Résultats par catégorie

La moyenne masque des différences importantes selon le type de question.

![nDCG@5 par catégorie de question et par stratégie](../figures/fig_recherche_categories.png){width=16cm}

Le graphe seul est la meilleure stratégie sur les questions relationnelles (0,96) et l'une des meilleures sur l'expertise (0,97), mais la moins bonne sur les questions factuelles (0,52) et ambiguës (0,37). BM25 domine sur les questions factuelles (0,99) et, à égalité avec le RAG hybride, sur les contradictions (0,92). L'architecture finale ne domine nulle part de façon spectaculaire, mais elle n'est mauvaise nulle part : elle atteint 0,99 sur le factuel, 0,86 sur le relationnel, 0,97 sur l'expertise et 0,71 sur le multi-sauts. C'est précisément le rôle attendu du routage : éviter que le graphe ne dégrade les questions simples tout en le mobilisant pour les questions relationnelles. Ces chiffres par catégorie reposent toutefois sur de petits effectifs (de 4 à 13 questions) et doivent être lus comme des tendances.

## Questions-réponses de bout en bout

### Comparaison des architectures

Le tableau suivant présente l'exactitude de bout en bout des cinq architectures, qui partagent le même workflow et le même générateur extractif.

| Architecture | Exactitude (66) | Questions répondables (55) | Développement (17) | Jamais inspectées (49) |
|---|---|---|---|---|
| RAG vectoriel | 0,651 [0,53 ; 0,76] | 0,582 | 0,882 | 0,571 |
| RAG hybride | 0,606 [0,48 ; 0,73] | 0,545 | 0,824 | 0,531 |
| GraphRAG | 0,515 [0,39 ; 0,64] | 0,418 | 0,706 | 0,449 |
| Hybride avec graphe (fixe) | 0,773 [0,67 ; 0,88] | 0,746 | 0,882 | 0,735 |
| Hybride final (routé) | 0,742 [0,64 ; 0,85] | 0,709 | 0,882 | 0,694 |

Table: Exactitude de bout en bout par architecture

![Questions-réponses : exactitude par architecture, sur l'ensemble et sur les questions jamais inspectées](../figures/fig_qa_architectures.png){width=15cm}

Les deux architectures qui combinent recherche hybride et graphe se détachent nettement. L'architecture finale dépasse le RAG hybride de 0,136 point [0,03 ; 0,24] (11 questions gagnées, 2 perdues, p = 0,02) et GraphRAG seul de 0,227 point [0,12 ; 0,33] (p < 0,001). L'écart avec le RAG vectoriel, 0,091 [0,00 ; 0,18], est plus incertain (p = 0,15).

Le résultat le plus inattendu est que la version **fixe** de l'architecture hybride avec graphe fait légèrement mieux que la version **routée** : 0,773 contre 0,742. L'écart porte sur deux questions seulement (p = 0,5) et n'est pas significatif, mais il va à l'encontre de ce que l'on attendait du routage, qui améliore en revanche la récupération (nDCG@5 0,839 contre 0,813). Le routage réduit le poids du graphe pour les questions classées comme factuelles ; certaines questions multi-documents ainsi classées perdent alors des faits utiles à la réponse. Le classifieur, qui s'accorde avec la catégorie annotée pour 88 % des questions comparables, n'est pas en cause en premier lieu : c'est la correspondance entre type de question et besoin en faits du graphe qui mériterait d'être affinée.

On remarque aussi que le RAG vectoriel fait mieux que le RAG hybride en exactitude (0,651 contre 0,606), alors qu'il est moins bon en récupération. L'explication tient à l'abstention : le RAG vectoriel s'abstient davantage à tort, mais les questions sur lesquelles il répond sont plus souvent justes, et il réussit les deux questions sans réponse que le RAG hybride manque. Cette inversion rappelle que la qualité de la récupération et l'exactitude de bout en bout ne se confondent pas.

### Fiabilité des réponses

Sur les 330 réponses produites par les cinq architectures, aucune ne contient de citation invalide, aucune ne contient de chaîne interdite et aucune n'expose d'information issue d'un document non autorisé. Le premier résultat découle du générateur extractif, qui ne peut citer qu'un passage effectivement présent ; les deux autres valident le contrôle d'accès appliqué en amont de la recherche et la mise en quarantaine du mémo piégé.

Cette dernière mesure appelle une réserve : dans la campagne principale, 62 des 66 questions sont posées avec le compte administrateur, qui voit tous les documents. Nous avons donc conduit un audit complémentaire, qui rejoue les 66 questions avec trois comptes restreints (diffusion générale seule, Conformité, DSI) et pour les cinq architectures, soit 990 réponses. Aucune ne contient de passage, de fait du graphe ou de preuve d'expertise issu d'un document non autorisé.

Pour l'architecture finale, 93 % des phrases des réponses sont appuyées par les sources qu'elles citent, et 96 % des réponses citent au moins un document indispensable. La précision des citations, part des documents cités qui font partie des documents de référence, est plus modeste (0,59) : les réponses citent aussi des documents connexes, pertinents pour le lecteur mais absents de nos annotations.

### Abstention, contradictions et ambiguïtés

L'architecture finale s'abstient sur 10 des 11 questions qui l'exigent (rappel d'abstention 0,909), y compris les deux questions de contrôle d'accès posées par un utilisateur non destinataire. La seule question sans réponse traitée à tort est une question de contrôle d'accès : l'assistant a produit une phrase sans rapport, issue d'un document autorisé, au lieu de s'abstenir. Il n'a rien divulgué du document restreint, mais sa réponse n'était pas pertinente.

L'abstention a un coût : 18 % des questions répondables donnent lieu à une abstention abusive. C'est la principale faiblesse mesurée, sur laquelle revient l'analyse d'erreurs. Les contradictions sont signalées pour trois des quatre questions qui en comportent, et les ambiguïtés pour trois sur quatre.

## Ablations du workflow

### Sensibilité au seuil de suffisance

Le seuil de suffisance règle le compromis entre abstention correcte et abstention abusive.

![Sensibilité de l'architecture finale au seuil de suffisance](../figures/fig_seuil_suffisance.png){width=15cm}

Abaisser le seuil à 0,35 réduit les abstentions abusives (12,7 %) mais laisse passer davantage de questions sans réponse (rappel d'abstention 0,727). Le relever à 0,65 garantit toutes les abstentions attendues, au prix de 21,8 % d'abstentions abusives. Le seuil de 0,55, fixé avant toute mesure, se situe au milieu de ce compromis. Dans un contexte bancaire, où une réponse erronée est plus dommageable qu'une absence de réponse, un seuil légèrement plus élevé pourrait se défendre ; ce choix relève d'un arbitrage métier plutôt que technique.

### Effet de la relance

Supprimer la relance du workflow ne change pas l'exactitude (0,742 dans les deux cas). La relance réduit légèrement les abstentions abusives (de 20,0 % à 18,2 %), mais elle déclenche aussi, pour certaines questions, une recherche plus large qui écarte des passages utiles trouvés au premier essai. Son apport net est nul sur ce banc d'essai. Nous la conservons parce qu'elle est bornée à une itération et que son coût est faible, mais ce résultat montre qu'une étape corrective n'est utile que si elle apporte une information réellement nouvelle.

## Recherche d'experts

| Méthode | Precision@1 | Recall@3 | nDCG@3 | MRR |
|---|---|---|---|---|
| Preuves typées pondérées | 1,000 | 0,967 | 0,975 [0,94 ; 1,00] | 1,000 |
| Nombre de mentions | 0,933 | 0,878 | 0,911 [0,78 ; 1,00] | 0,944 |

Table: Recherche d'experts sur 15 domaines

![Recherche d'experts : comparaison avec le comptage de mentions](../figures/fig_experts.png){width=15cm}

Le score fondé sur des preuves typées place un expert en première position pour les quinze domaines. Il fait mieux que le comptage de mentions sur quatre domaines et moins bien sur un seul. L'écart de nDCG@3, 0,064 [−0,02 ; 0,19], n'est cependant pas significatif (p = 0,375) : la référence naïve est déjà bonne sur ce corpus, où les experts sont souvent aussi les personnes les plus citées. Les cas où elle échoue sont instructifs : pour la continuité d'activité, le comptage de mentions classe en deuxième position une personne très citée dans le plan de continuité sans en être experte, alors que le score typé retient le responsable désigné.

## Recommandations

| Mode | Precision@5 | Recall@5 | nDCG@5 | MRR |
|---|---|---|---|---|
| Contenu seul | 0,440 | 0,497 | 0,648 [0,50 ; 0,79] | 0,920 |
| Graphe seul | 0,660 | 0,818 | 0,877 [0,70 ; 0,98] | 0,950 |
| Hybride | 0,640 | 0,784 | 0,908 [0,80 ; 0,97] | 1,000 |

Table: Recommandations sur 10 documents sources

![Recommandations : comparaison des modes contenu, graphe et hybride](../figures/fig_recommandations.png){width=15cm}

La combinaison du contenu et du graphe améliore nettement la seule similarité de contenu : +0,261 de nDCG@5, avec neuf documents sources gagnés et aucun perdu (p = 0,004). Le graphe apporte des liens que le contenu ne voit pas : version antérieure d'une procédure, rapport d'audit portant sur le même dispositif, fiche du projet qui l'a fait évoluer. Aucun mode ne recommande les doublons ni le mémo piégé.

## Analyse d'erreurs

L'examen des 17 questions mal traitées par l'architecture finale fait apparaître quatre causes principales.

**Des abstentions abusives liées au vocabulaire de la question.** Neuf échecs sont des abstentions. Dans plusieurs cas, le contexte contenait la réponse, mais un terme de la question était absent des documents : « intervenu » (« Sur quels projets Amine Kettani est-il intervenu ? »), « composent » (« Quelles entités composent la DSI ? »), « évoluer ». Le contrôle de suffisance, fondé sur la présence des termes, ne reconnaît pas les paraphrases. L'analyse a aussi révélé un défaut plus simple : le verbe « être » ne figure pas dans la liste des mots vides et peut être compté comme un terme manquant, comme pour la question sur le délai d'accusé de réception. Nous ne l'avons pas corrigé après le gel, pour ne pas modifier la configuration évaluée, et le signalons comme une amélioration évidente.

**Des questions qui demandent un jugement.** Certaines questions multi-documents appellent une conclusion : « Le délai d'escalade a-t-il été respecté lors de l'incident ? » ou « Le paramétrage de l'outil est-il conforme à la procédure ? ». Le générateur extractif retrouve les deux éléments à comparer, mais ne peut pas écrire « non, l'escalade a eu lieu après plus de deux heures ». Ces questions sont celles pour lesquelles un LLM apporterait le plus.

**Des chaînes multi-sauts incomplètes.** Pour les questions multi-sauts, le graphe trouve la plupart des maillons, mais pas toujours le dernier : par exemple, cinq des six applications affectées par l'indisponibilité du système central sont citées, la sixième dépendant d'une relation non extraite. Ces échecs prolongent ceux de l'extraction : une relation manquante dans le graphe interrompt la chaîne de raisonnement.

**Une question ambiguë trop vague.** À la question « Comment se déroule la revue ? », le système s'abstient au lieu de signaler les différentes revues possibles (revue périodique des clients, revue des habilitations).

## Modification post-gel

La garantie par source dans la fusion, ajoutée après la campagne principale pour corriger le cas décrit au chapitre 5, a été évaluée séparément.

| Mesure (architecture finale) | Configuration gelée | Après modification |
|---|---|---|
| Recherche, nDCG@5 | 0,839 | 0,841 |
| Recherche, nDCG@5 (jamais inspectées) | 0,851 | 0,854 |
| Couverture des preuves | 0,943 | 0,953 |
| Exactitude | 0,742 | 0,758 |
| Exactitude (développement) | 0,882 | 0,941 |
| Exactitude (jamais inspectées) | 0,694 | 0,694 |

Table: Effet de la modification post-gel

Le gain d'exactitude se concentre sur les questions de développement, où se trouvait le cas qui a motivé la modification. Sur les questions jamais inspectées, l'exactitude est inchangée, et seule la récupération progresse légèrement. Ce résultat illustre l'intérêt du protocole : sans la distinction entre les deux groupes de questions, on aurait pu attribuer à la modification un gain général qu'elle n'apporte pas.

## Discussion des hypothèses

**H1 (graphe et questions relationnelles) : partiellement validée.** Sur les questions relationnelles, l'architecture finale obtient un nDCG@5 de 0,86, contre 0,81 pour le RAG vectoriel, mais au même niveau que le RAG hybride (0,86) ; sur les questions multi-sauts, elle atteint 0,71 contre 0,55 et 0,63. Le gain sur le RAG vectoriel est net, mais l'écart avec le RAG hybride est nul sur le relationnel et modéré sur le multi-sauts, sur 8 et 10 questions seulement. Le graphe seul fait mieux encore sur le relationnel (0,96), ce qui suggère que la fusion dilue en partie son apport.

**H2 (pas de dégradation du factuel) : validée.** Sur les 13 questions factuelles, l'architecture finale atteint un nDCG@5 de 0,99, au niveau de BM25 et au-dessus du RAG hybride (0,93), et une exactitude de 0,92, identique à celle des RAG vectoriel et hybride. Le graphe seul, sans routage, tombe à 0,52 : c'est bien le routage qui protège les questions simples.

**H3 (abstention à bon escient) : partiellement validée.** Le rappel d'abstention est élevé (0,909) et aucune information restreinte n'a fuité, mais le taux d'abstentions abusives (18 %) est trop élevé pour un usage quotidien, et la précision d'abstention n'est que de 0,5.

**H4 (experts) : non démontrée.** Le score typé fait mieux que le comptage de mentions sur tous les indicateurs, mais l'écart n'est pas significatif sur quinze domaines. L'avantage qualitatif, une justification par des preuves, reste réel.

**H5 (recommandations) : validée.** L'hybride surpasse nettement la seule similarité de contenu (+0,261 de nDCG@5, p = 0,004).

## Menaces à la validité

**Validité interne.** Le corpus, les annotations, les règles et les heuristiques ont été conçus par la même personne. Malgré la partition des documents, le gel de la configuration et la distinction des questions de développement, un biais de conception subsiste. L'écart d'exactitude entre questions de développement (0,882) et questions jamais inspectées (0,694) en donne la mesure : une partie de la performance observée sur les premières tient à la mise au point. Les résultats sur les questions jamais inspectées sont les plus représentatifs.

**Validité externe.** Le corpus est synthétique, de petite taille et plus régulier que la réalité. Des documents réels présenteraient davantage de variations de forme, des tableaux complexes, des fautes et des formulations imprévues, qui pèseraient en particulier sur l'extraction par règles. Les résultats valent pour ce banc d'essai.

**Validité de construit.** L'exactitude par mots-clés mesure la présence des éléments attendus, pas la qualité d'ensemble d'une réponse. L'appui des phrases sur les sources est une approximation lexicale de la fidélité. Ces mesures sont adaptées à un générateur extractif ; avec un LLM, il faudrait les compléter par une évaluation humaine ou par des métriques comme celles de RAGAS (Es et al., 2024), en tenant compte des biais des LLM utilisés comme juges (Zheng et al., 2023).

**Validité de conclusion.** Avec 66 questions, les intervalles de confiance sont larges et plusieurs écarts ne sont pas significatifs. Nous nous sommes efforcée de ne conclure que lorsque l'incertitude le permettait.
