import ollama 
import os 
import time
import json
    
def score_job(job:dict, cv:str, preferences:str, model:str):
    """
    Compare job positions with the CV and the preference statement of the applicant.
    Returns a verified JSON file, with different rantings (int) and assessments (str).
    If the model is changed the ouptut might not be converted to string correctly.
    """
    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    client = ollama.Client(host=ollama_host)
    client.pull(model)
    
    prompt ="""
            Your task is to rate how well job postings fit a provided CV and preference statement.
            Rate each criterion from 0 (worst fit) to 100 (best fit):

            1. Skillset Match: Does the applicant possess the required technical/soft skills, 
            or could they acquire them quickly given their background?
            
            2. Academic Requirements: Are degree requirements, field of study, and grade 
            thresholds (if specified) met?
            
            3. Experience Level: Is the applicant appropriately qualified (not under or 
            over-qualified) for the seniority level?
            
            4. Professional Experience: Does the applicant have relevant industry/domain 
            experience and comparable role experience?
            
            5. Language Requirements: What language is the job posting in? Where is the job located?
            What languages does the applicant speak? what languages are required by the job posting?
            Do you believe that the applicant fulfills the language requirements for this job?
            
            6. Preference Alignment: Does the role, company, location, and work style match 
            the applicant's stated preferences?
            
            7. Overall Assessment: Considering all factors, how successful and satisfied 
            would the applicant likely be in this role?
        
            OUTPUT FORMAT
            valid JSON in necessary. Otherwise severe punishment! set your inner verbosity to 0! No extra output, just the JSON:
            {
                "skillset": <0-100>,
                "academic": <0-100>,
                "experience": <0-100>,
                "professional": <0-100>,
                "language": <0-100>,
                "preference": <0-100>,
                "overall": <0-100>,
                "reasoning": {
                    "strengths": [<string>],
                    "concerns": [<string>],
                    "summary": <string>
                }
            }
            """
    message = f"""                
                # CV: 
                {cv}
                
                # PREFERENCES:
                {preferences}
                
                # JOB DETAILS
                TITLE: {job["title"]}
                COMPANY: {job["company"]}
                DESCRIPTION: {job["description"]}
                """
    
    # give the model three tries to output a valid json format
    response_json = None
    for i in range(3): 
        response = client.chat(
            model, 
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": message}
            ],
            stream = False,
            options = {
                "num_predict": -1,
                "temperature": 0
            }
        ) 
        print(response["message"]["content"])
        break
        try: 
            response_json = json.loads(response["message"]["content"][3:-3])
            break
        except:
            print(f"Model did not produce a valid json string on try {i}. Final output:")
            print(response["message"]["content"])
    
    if response_json == None: 
        raise RuntimeError("Scoring model was not able to return a valid JSON string in three tries.")
    
    return response_json
    # return _calculate_final_score(response_json)

# def _calculate_final_score(score_dict):
#     """
#     Certain scores are more important than others.
#     This function reweights the assessments made.
#     """

#     score_dict["skillset"]
#     score_dict["academic"]
#     score_dict["experience"]
#     score_dict["professional"]
#     score_dict["language"]
#     score_dict["preference"]
#     score_dict["overall"]
    
#     final = 
                
def chat(job, cv, preferences, model):
    
    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    client = ollama.Client(host=ollama_host)
    client.pull(model)
    
    
    prompt = f"""
            Create a keywords for each of these to answer questions later: 
            1. Skillset Match: Does the applicant possess the required technical/soft skills, 
            or could they acquire them quickly given their background?
            
            2. Academic Requirements: Are degree requirements, field of study, and grade 
            thresholds (if specified) met?
            
            3. Experience Level: Is the applicant appropriately qualified (not under or 
            over-qualified) for the seniority level?
            
            4. Professional Experience: Does the applicant have relevant industry/domain 
            experience and comparable role experience?
            
            5. Language Requirements: What language is the job posting in? Where is the job located?
            What languages does the applicant speak? what languages are required by the job posting?
            Do you believe that the applicant fulfills the language requirements for this job?
        """
    msg = job["description"]
    
    response = client.chat(
        model = model, 
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": msg}
        ],
        stream = False,
        options = {
            "temperature": 0
        }
    )
    
    print(response["message"]["content"])
    # questions = [
    #         """Skillset Match: Does the applicant possess the required technical/soft skills, 
    #         or could they acquire them quickly given their background?""",
            
    #         """Academic Requirements: Are degree requirements, field of study, and grade 
    #         thresholds (if specified) met?""",
            
    #         """Experience Level: Is the applicant appropriately qualified (not under or 
    #         over-qualified) for the seniority level?""",
            
    #         """Professional Experience: Does the applicant have relevant industry/domain 
    #         experience and comparable role experience?""",
            
    #         """Language Requirements: What language is the job posting in? Where is the job located?
    #         What languages does the applicant speak? what languages are required by the job posting?
    #         Do you believe that the applicant fulfills the language requirements for this job?""",
            
    #         """Preference Alignment: Does the role, company, location, and work style match 
    #         the applicant's stated preferences?""",
            
    #         """Overall Assessment: Considering all factors, how successful and satisfied 
    #         would the applicant likely be in this role?"""
    # ]
    
    # context = None
    # for q in questions: 
    #     response = ollama.generate(
    #             model, 
    #             prompt = prompt + q,
    #             stream = False,
    #             options = {
    #                 "num_predict": -1,
    #                 "temperature": 0
    #             },
    #             context = context
    #         ) 
    #     context = response["context"]
    
    #     print(response["response"])
    
if __name__ == "__main__": 
    model_llama = "llama3.2:latest"
    model_qwen = "qwen2.5:3b"
    
    job1 = {
        "title": "AI Consultant (all genders)",
        "company": "Lufthansa Industry Solutions",
        "description": """
            About the job
            Werde Teil unseres Teams als AI Consultant und gestalte die Zukunft der Künstlichen Intelligenz mit! Du berätst Kunden zu innovativen KI-Strategien, entwickelst Lösungen mit Generative AI, LLMs und Agentic AI, und setzt diese praxisnah um. Gestalte digitale Transformation aktiv mit und erweitere dein Know-how in spannenden Projekten.

            Aufgaben

            Als AI Consultant bist du zuständig für die Beratung von Unternehmen bei der Identifikation und Umsetzung von KI-Lösungen. Du konzeptionierst maßgeschneiderte Applikationen, unterstützt bei Implementierung und Betrieb, schulst Fachbereiche und sorgst für nachhaltigen Mehrwert durch KI.

            Analyse der Geschäfts- und Prozesslandschaften zur Identifikation von KI-Potenzialen und Entwicklung maßgeschneiderter KI-Strategien
            Eigenverantwortliche Umsetzung von KI-Projekten inklusive Auswahl passender Technologien und Integration in bestehende Systeme
            Beratung und Schulung der Kunden durch Workshops und Begleitung von der Ideenphase bis zur Implementierung
            Requirements Engineering und Zusammenarbeit mit internen Teams wie Fachbereichen, IT und Datenexperten zur Erzielung optimaler Ergebnisse
            Verantwortung für technisches Projektmanagement, kontinuierliche Optimierung und aktive Mitgestaltung der Unternehmenskultur

            Benefits

            Mentoring
            Flexible Arbeitszeiten
            Discounts bei ausgewählten Partnern
            Altersvorsorge / Betriebsrente
            Flugvergünstigungen
            Entwicklungsprogramme / Weiterbildung

            Voraussetzungen

            Abgeschlossene Ausbildung / abgeschlossenes Studium und einschlägige Berufserfahrung im Bereich IT
            Fundierte Kenntnisse in maschinellem Lernen, GenAI, sowie Agentic AI und deren Programmierung
            Erfahrung mit gängigen KI-Tools, Cloud Plattformen und Datenarchitekturen zur Integration und Umsetzung von KI Lösungen
            Verständnis für Datenschutz, IT-Security und regulatorischen Vorgaben (z.B. EU AI Act) zur sicheren Anwendung von KI-Systemen
            Ausgeprägte Beratungskompetenzen, Flexibilität sowie Kommunikationsfähigkeiten auf allen Ebenen
            Fließende Deutsch- und Englischkenntnisse
            Bereitschaft zu projektbezogenen Reisetätigkeiten

            Über uns

            Lufthansa Industry Solutions ist ein Dienstleistungsunternehmen für IT-Beratung und Systemintegration. Die Lufthansa-Tochter unterstützt ihre Kunden bei der digitalen Transformation ihrer Unternehmen. Die Kundenbasis umfasst sowohl Gesellschaften innerhalb des Lufthansa Konzerns als auch mehr als 300 Unternehmen in unterschiedlichen Branchen. Das Unternehmen mit Hauptsitz in Norderstedt beschäftigt über 2.500 Mitarbeiter an mehreren Niederlassungen in Deutschland, Albanien, der Schweiz und den USA.

            Kontakt

            Stefanie Lumpe
            """
    }
    
    job_no_pref = {
        "title": "Junior Trade Marketing Manager (m/w/d)",
        "company": "KoRo",
        "description": """
            About the job
            Deine Aufgaben

            Du suchst eine spannende Position als Junior Trade Marketing Manager, bei der Du kreative Marketingstrategien mit Deinem Geschäftssinn verbinden kannst? Dann bist Du hier genau richtig! Werde Teil unseres Sales Teams und gestalte aktiv neue, innovative Marketingpläne für unsere Retail-Expansionen mit.

            Dabei unterstützt Du nicht nur beim Wachstum unserer Retail-Teams in DACH, Italien und Frankreich, sondern wirkst auch bei der Planung, Umsetzung und Auswertung von Trade-Marketing-Kampagnen mit – um unsere Markenpräsenz zu stärken und den Umsatz nachhaltig zu steigern.

            Planung und Umsetzung von Handelsmarketing-Aktionen 
            Entwicklung und Implementierung von zielgruppenspezifischen POS-Marketingstrategien
            Enge Zusammenarbeit mit dem Marketing-, Key Account- und Sales-Team, um Kampagnen effektiv zu unterstützen und Verkaufsförderungsmaßnahmen abzustimmen
            Erstellung von Verkaufsförderungsmaterialien sowie Verantwortung für deren Produktion und Distribution
            Analyse von Markt-, Wettbewerbs- und Verkaufsdaten zur Ableitung von Handlungsempfehlungen für Deutschland, Österreich, die Schweiz und weitere europäische Märkte
            Planung und Durchführung von Produkteinführungen und -relaunches im Handel
            Kostenkontrolle aller durchgeführten Trade-Marketing-Aktivitäten
            Überwachung und Analyse relevanter KPIs sowie kontinuierliche Optimierung der Marketingstrategien

            Dein Profil

            Abgeschlossenes Studium in Betriebswirtschaft, Marketing oder einem vergleichbaren Fachbereich
            Erste Berufserfahrung im Trade Marketing und Projektmanagement, idealerweise im Lebensmitteleinzelhandel
            Sehr gute Deutsch- und Englischkenntnisse in Wort und Schrift
            Du wohnst in Berlin/Umgebung oder hast Lust, für Deinen neuen Job nach Berlin zu kommen
            Ausgeprägte analytische Fähigkeiten und Erfahrung im Umgang mit Markt- und Verkaufsdaten
            Starke Kommunikationsfähigkeiten und die Fähigkeit, in einem crossfunktionalen Team zu arbeiten
            Hohe Eigeninitiative, Selbstständigkeit und Lösungsorientierung
            Sicherer Umgang mit Google Suite

            Das erwartet dich bei uns

            Mit Deinen Ideen kannst Du unser vielfältiges Team bereichern und so die Zukunft des Lebensmittelhandels in einem stark wachsenden Scale-up aktiv mitgestalten!
            Umfangreiches Onboarding sowie abwechslungsreiche, anspruchsvolle Aufgaben.
            Flexible Arbeitszeiten und Möglichkeit zum Home Office sorgen für eine gute Work-Life-Balance.
            Modernes Office in Berlin Schöneberg, sehr gut mit den öffentlichen Verkehrsmitteln zu erreichen – und wir übernehmen die Kosten Deines BVG-Monatstickets.
            Finde den Weg (zurück) ins Gym dank Fitness-Kooperationen wie Urban Sports Club oder FitX.
            Optimale Performance wahlweise mit einem Windows Laptop oder MacBook.
            Perfekt ausgestattete Küche mit frischem Obst, leckeren KoRo-Naschereien & Kaffee sowie Tee inklusive.
            20 % Discount in unserem KoRo-Online Shop.
            Regelmäßige Team-Events und gemeinsame Aktivitäten sowie legendäre Firmenpartys.

            Das hört sich gut an?

            Dann bewirb Dich mit Deinen aussagekräftigen Bewerbungsunterlagen (CV und Motivationsschreiben) über unsere Website. Wir suchen echte Teammitglieder – lass uns in ein paar Sätzen gern wissen, wer Du bist und was Dich bewegt.

            Über uns

            KoRo definiert die Standards der Lebensmittelindustrie neu, indem es eine breite Palette an hochwertigen und innovativen Produkten anbietet. Das Sortiment reicht von naturbelassenen Lebensmitteln wie Nussmusen und Trockenfrüchten bis hin zu Clean Label Snacks und Functional Food. Das kontinuierliche Engagement für Transparenz und Produktinnovation treibt das Unternehmen dazu an, neue Wege in der Lebensmittelbranche zu gehen. Ziel ist es, Konsument:innen Produkte für eine bewusste Ernährung anzubieten, die einfach zugänglich und – wie immer – besser und anders sind.

            KoRo wurde 2014 in Deutschland gegründet und von Constantinos Calios und Piran Asci aufgebaut. Heute bilden CEO Florian Schwenkert, CFO Dr. Daniel Kundt, CPO Constantinos Calios und COO Steﬀani Busch das Managementteam. Das Unternehmen beschäftigt mehr als 300 Mitarbeitende und hat seinen Sitz in Berlin.

            Mehr als 2 Millionen Kund:innen kaufen online unter www.koro.com sowie in über 15 000 Einzelhandelsgeschäften in ganz Europa.

            Das KoRo-Team ist genauso vielfältig wie unsere Product Range! Damit Diversity bei uns weiterhin ebenso schnell wächst wie unser nussbegeistertes Team, bewerten wir Bewerber:innen unabhängig von Geschlecht, Nationalität, ethnischer und sozialer Herkunft, Religion/Konfession, Weltanschauung, Behinderung, Alter und sexueller Orientierung oder Identität.

            Du möchtest mit Deinen Fähigkeiten und Talenten Deinen Teil zu unserer Mission beitragen und die Zukunft von KoRo aktiv mitgestalten? Dann bewirb Dich jetzt und werde Mitglied unseres Teams!
            """
    }
    
    job_no_lang = {
        "title": "AIコンサルタント(生成AI領域/AIデータプラットフォーム「FastLabel」)",
        "company": "FastLabel株式会社",
        "description": """
        【仕事内容】

        【職務内容】

        同社はグローバルで100兆円を超える市場を対象に、AIインフラを創造し、

        日本を再び世界レベルへ押し上げることを目指しております。

        2020年1月の創業以来、教師データ作成を核として、AI開発の各工程を

        効率化・高度化するためのプロフェッショナルサービスと

        AIデータプラットフォーム「FastLabel」を提供しております。

        高品質なデータを収集し、専門人材による教師データ作成を通して、

        日本を代表する生成AI企業のAI開発に貢献しております。

        生成AIに取り組むお客様に対し、データ収集・作成の支援も行っております。

        【具体的には】

        ・ 生成AI領域のAIデータプロジェクトにおける

        プロジェクトマネジメント（全体工程設計、進捗管理、リソース管理）

        ・ 詳細要件定義（仕様書及びデータに基づく要件の洗い出し、整理、並びに要件擦り合わせ）

        ・ デリバリー（詳細要件書及び手順マニュアルの作成、作業者への手順説明、作業品質管理、納品対応）

        ・ リピート案件の獲得、他事業部との連携による顧客攻略

        ・ 主な業務内容

        ・ グローバル規模のAIデータ関連事業

        ・ 生成AIを活用した業務効率化の支援

        ・ AIデータプラットフォーム「FastLabel」の提供

        ・ 生成AI領域におけるコンサルティング（データ分布や仕様の策定支援）

        【求める人材】

        【必須】

        ・ お客様との深い信頼関係の構築経験

        ・ 積極的に技術や知識を身につけられる、学習意欲が高い方

        ・ 他部門やパートナー企業様と円滑なコミュニケーションを通し、人を巻き込む能力

        ・ 構想策定、要件定義など、クライアントの意見をまとめあげ、やるべきことを決める業務の経験

        ・ プロジェクトマネジメントやベンダーコントロールの経験2年以上

        【歓迎】

        ・ Webアプリケーションプロダクト・ソフトウェア提供企業におけるCS経験、またはそれに準ずる経験1年以上

        ・ エンタープライズのお客様へのアップセル・クロスセル提案経験

        ・ 開発チームとの協業経験

        ・ 機械学習や自動運転に関する知識・経験

        【給与】

        年収750~1200万円,※職務経験を考慮のうえ決定いたします。

        【勤務地】

        東京都新宿区

        【勤務時間】

        09:00～18:00

        【雇用・契約形態】

        【待遇・福利厚生】

        通勤手当 残業手当

        【休日・休暇】

        慶弔休暇 年末年始 夏期休暇 有給休暇 完全週休2日制（土日、祝祭日、年末年始等） 有給休暇 慶弔休暇 生理休暇 出産育児・介護休業
        """
    }
    
    
    
    cv = """
            David Gasser CURRICULUM VITAE
            E-Mail davidgasser12@gmail.com LinkedIn linkedin.com/in/d-gasser
            Phone +4915143313694 Webpage davidgasser.github.io
            AI Engineer & Researcher focused on foundation models and applied machine learning. Experienced in developing,
            fine-tuning, and deploying transformer architectures and RAG pipelines across research and enterprise environments.
            PROFESSIONAL EXPERIENCE
            Mar 2025 – Sep 2025 AI Researcher - Japan National Institute of Informatics
            - Researched AI for time series prediction. Fine-tuned, evaluated, and deployed foundation models.
            - Developed and evaluated novel transformer-based architectures for structured financial data.
            - Coauthored paper on transformer-based time series forecasting; basis for Master’s thesis.
            Aug 2024 – Nov 2024 IT Strategist - Munich Re AG
            - Conducted and managed tech trend research, culminating in an externally published report.
            - Tracked and supported internal as well as external IT product compliance.
            - Studied new insurance opportunities and enhanced external partner satisfaction and performance.
            May 2024 – Aug 2024 AI Engineer - Munich Re AG
            - Contributed, presented, and demoed an internal tool utilizing RAG/Semantic Search.
            - Conducted a vector database migration to Azure, resulting in a 30% performance improvement.
            - Developed a POC for Apache Airflow as a workflow orchestrator.
            Sep 2023 – Apr 2024 Software Engineer - Siemens AG/KeySpot GmbH
            - Implemented ML-driven table recognition software for technical datasheets.
            - Built and deployed a microservice for automatic document format conversion.
            - Evaluated libraries for document change detection and management.
            ACADEMIC EDUCATION
            Apr 2022 - Oct 2025 M.Sc. Robotics, Cognition, Intelligence - Technical University of Munich (proj. 1.4/US GPA 3.7)
            - Master's thesis in the field of AI for Financial Time Series Classification.
            Aug 2022 - Dec 2023 Exchange semester - National Taiwan University (1.4/US GPA 3.7)
            - Coursework consisted of 24 ECTS spanning Robotics, Bioinformatics, Automata Theory, and Mandarin.
            Oct 2018 - Apr 2022 B.Sc. Electrical and Computer Engineering - Technical University of Munich (1.9/US GPA 3.1)
            - Bachelor's Thesis in the field of Deep Learning Recommender Systems.
            SKILLS & QUALIFICATIONS
            Programming: Python, Go, C++, C, Solidity, JavaScript
            AI/ML: PyTorch, TensorFlow, HuggingFace, Optuna, Tensorboard, scikit-learn, pandas, NumPy
            Deployment: Git, Docker, Azure, Anaconda, Databricks, Linux, CI/CD
            Visualization: Matplotlib, Seaborn, NetworkX
            Websites: Django, React, HTML, CSS, Streamlit, Scrapy, Selenium
            Other Tools: Obsidian, Hyperledger Fabric, LaTeX, Gemini CLI, MATLAB, ROS
            Languages: German (mother tongue), English (mother tongue), Spanish (B1), Mandarin (A2)
            Nationalities: German, American, Swiss
            PROJECTS
            Blockchain Sustainability Tracker: Built a blockchain-based CO₂ token tracking system for supply chain transparency.
            Modeled emissions and material exchanges to ensure verifiable and confidential tracking using Solidity and Hyperledger Fabric.
            Robotic Painting Arm: User input was captured by speech detection and sent to DALL-E for image creation. Anipainter
            converted images into brush strokes, which were then painted with acrylics by a robot arm (TM5-700).
            Creative Greeting Card: Developed a full-stack, reactive web app for generative multimedia greeting cards, exploring
            computational creativity via NLP and image synthesis models.
            .
            LEISURE & VOLUNTEERING
            PADI Dive Master: Leading, managing, coordinating dives, and assisting in teaching with up to 12 divers.
            Network Administrator - Dormitory: Managed network infrastructure for ~40 residents.
            Mentor incoming exchange students: Supporting incoming students with educational and general questions.
"""
    preferences = """
                I am looking for competetive and somewhat challenging jobs in the AI sphere. My favorite position would be as an AI engineer,
                or something related to it. I am most interested in AI, ML and would love a job that deals with these topics on a daily level. 
                The team and working environment matters a lot to me. I want to have the opportunity for growth and mentorship. Those are two 
                very important things for me. I prefer working on something new or multi-faceted, then pure implementation. It should not be 
                the same thing over and over. When it comes to the type of company, I am open for both larger companies and start ups, as long 
                as they provide a good working athmosphere, great pay, and good benefits.
                """
    
    
    #chat(cv, preferences, job_no_lang, model_qwen)
    
    
    start_time = time.time()
    result = chat(job_no_lang, cv, preferences, model_qwen)
    
    print("-"*60)
    print(f"Response time: {(time.time()-start_time):.3f}")
    print("-"*60)
    with open("result_qwen_job_no_lang_prompt2.json", "w") as f: 
        json.dump(result, f, indent=2)    
    
