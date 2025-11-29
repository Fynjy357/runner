#!src/mail_service/email_templates.py
"""
Шаблоны email писем
"""

from typing import Tuple, Dict, Any
from datetime import datetime

class EmailTemplates:
    def __init__(self):
        self.templates = {
            'welcome': self.welcome_template,
            'completion': self.completion_template,
            'test': self.test_template,
            'universal_link': self.universal_link_template  # Основной шаблон с Telegram ссылкой
        }
    
    def get_template(self, template_name: str, recipient_data: Dict[str, Any]) -> Tuple[str, str, str]:
        """Получение шаблона по имени"""
        if template_name not in self.templates:
            raise ValueError(f"Шаблон {template_name} не найден")
        
        return self.templates[template_name](recipient_data)
    
    def universal_link_template(self, recipient: Dict[str, Any]) -> Tuple[str, str, str]:
        """Шаблон приветственного письма с Telegram ссылкой"""
        
        # Данные получателя
        first_name = recipient.get('first_name', '')
        last_name = recipient.get('last_name', '')
        universal_link = recipient.get('universal_link', '#')
        stage_name = recipient.get('stage_name', 'новогодний квест')
        
        # Формируем обращение
        if first_name and last_name:
            greeting = f"{first_name} {last_name}"
        elif first_name:
            greeting = first_name
        else:
            greeting = "Уважаемый участник"
        
        subject = f"🎄 Добро пожаловать в Новогодний Квест. {stage_name}!"
        
        # HTML версия
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8f9fa;
                }}
                .container {{
                    background: white;
                    border-radius: 15px;
                    overflow: hidden;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                }}
                .header-img {{
                    width: 100%;
                    height: auto;
                    display: block;
                    border-bottom: 4px solid #ff6b6b;
                }}
                .content {{
                    padding: 30px;
                }}
                .greeting {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #2c3e50;
                    margin-bottom: 20px;
                    text-align: left;
                }}
                .stage-info {{
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                    padding: 15px;
                    border-radius: 10px;
                    margin: 20px 0;
                    text-align: center;
                    font-weight: bold;
                    font-size: 18px;
                }}
                .button {{
                    display: block;
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white !important;
                    padding: 18px 30px;
                    text-decoration: none;
                    border-radius: 30px;
                    font-weight: bold;
                    margin: 25px auto;
                    text-align: center;
                    font-size: 18px;
                    width: 80%;
                    max-width: 300px;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
                    transition: transform 0.3s ease;
                }}
                .button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
                }}
                .steps {{
                    background: #f8f9fa;
                    padding: 25px;
                    border-radius: 10px;
                    margin: 25px 0;
                    border-left: 5px solid #667eea;
                }}
                .step {{
                    margin: 12px 0;
                    padding-left: 25px;
                    position: relative;
                }}
                .step:before {{
                    content: "✓";
                    position: absolute;
                    left: 0;
                    color: #27ae60;
                    font-weight: bold;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 2px solid #eee;
                    color: #666;
                }}
                .highlight {{
                    background: #fff3cd;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px 0;
                    border: 2px solid #ffeaa7;
                }}
                .telegram-help {{
                    background: #e7f3ff;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 25px 0;
                    border: 2px solid #a5d8ff;
                }}
                .link-box {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 15px 0;
                    border: 1px dashed #667eea;
                    word-break: break-all;
                    font-family: 'Courier New', monospace;
                    font-size: 14px;
                }}
                @media (max-width: 480px) {{
                    .content {{
                        padding: 20px;
                    }}
                    .greeting {{
                        font-size: 20px;
                    }}
                    .button {{
                        width: 90%;
                        padding: 15px 20px;
                        font-size: 16px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <!-- Адаптивная картинка в шапке -->
                <img src="cid:header_image" alt="🎄 Новогоднее Приключение" class="header-img">
                
                <div class="content">
                    <div class="greeting">
                        Здравствуйте, {first_name or 'Участник'}! 🎅
                    </div>

                    <p>Добро пожаловать в уникальное событие! Благодарим, что выбрали именно наш старт! 🎉</p>
                    
                    <p>Теперь Вы стали частью чего-то поистине волшебного — это не просто забег, а настоящее приключение, которое запомнится надолго!</p>

                    <div class="stage-info">
                        🎯 Этап: <strong>{stage_name}</strong>
                    </div>
                    
                    <div style="text-align: center;">
                        <h3 style="color: #2c3e50; margin-bottom: 20px;">🚀 Ваше уникальное приключение начинается в нашем Telegram боте</h3>
                        
                        <a href="{universal_link}" class="button" style="color: white !important; text-decoration: none;">
                            📱 Начать Квест в Telegram!
                        </a>
                    </div>

                    <div class="steps">
                        <h4 style="color: #667eea; margin-top: 0;">📋 Как начать квест:</h4>
                        <div class="step">Нажмите на кнопку выше или скопируйте ссылку ниже</div>
                        <div class="step">Откроется Telegram с нашим ботом</div>
                        <div class="step">Нажмите кнопку "START" или "Запустить"</div>
                        <div class="step">Следуйте инструкциям бота и получайте задания</div>
                    </div>

                    <div class="highlight">
                        <p style="margin-top: 0;"><strong>🔗 Ваша персональная ссылка для доступа к "{stage_name}":</strong></p>
                        <div class="link-box">
                            {universal_link}
                        </div>
                        <p style="margin-bottom: 0; font-size: 14px; color: #666;">
                            ⚠️ Будьте внимательны, ссылка одноразовая!
                        </p>
                    </div>

                    <div class="telegram-help">
                        <h4 style="color: #0088cc; margin-top: 0;">📱 У вас нет Telegram?</h4>
                        <p>Скачайте приложение Telegram из App Store или Google Play, затем перейдите по ссылке выше.</p>
                        <p><strong>💬 Нужна помощь?</strong> Если у вас возникнут вопросы или потребуется помощь, не стесняйтесь обращаться к нашей команде поддержки.</p>
                    </div>

                    <p style="text-align: center; font-size: 18px; font-weight: bold;">
                        Желаем незабываемых эмоций на старте! ✨
                    </p>

                    <div class="footer">
                        <p style="font-size: 16px; color: #667eea; font-weight: bold;">
                            С любовью, команда «Стартани»! ❤️
                        </p>
                        <p style="font-size: 12px; color: #999;">
                            Это автоматическое письмо, пожалуйста, не отвечайте на него.
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Текстовая версия остается без изменений
        text_content = f"""
        Добро пожаловать в новогоднее приключение!

        Здравствуйте, {first_name or 'Участник'}!

        Добро пожаловать в уникальное событие! Благодарим, что выбрали именно наш старт! 🎉

        Теперь Вы стали частью чего-то поистине волшебного — это не просто забег, а настоящее приключение, которое запомнится надолго!

        🚀 Ваше уникальное приключение начинается в нашем Telegram боте:

        🎯 Этап: {stage_name}

        📱 Начать Квест в Telegram!
        {universal_link}

        📋 КАК НАЧАТЬ КВЕСТ:
        1. Нажмите на ссылку выше
        2. Откроется Telegram с нашим ботом
        3. Нажмите кнопку "START" или "Запустить"
        4. Следуйте инструкциям бота и получайте задания

        🔗 Ваша персональная ссылка для доступа к этапу "{stage_name}":
        {universal_link}

        📱 У ВАС НЕТ TELEGRAM?
        Скачайте приложение Telegram из App Store или Google Play, затем перейдите по ссылке выше.

        💬 НУЖНА ПОМОЩЬ?
        Если у вас возникнут вопросы или потребуется помощь, не стесняйтесь обращаться к нашей команде поддержки.

        Желаем незабываемых эмоций на старте!

        С любовью, команда «Стартани»!

        ---
        Это автоматическое письмо, пожалуйста, не отвечайте на него.
        """
        
        return subject, html_content, text_content


    
    def welcome_template(self, recipient: Dict[str, Any]) -> Tuple[str, str, str]:
        """Стандартный приветственный шаблон (запасной)"""
        first_name = recipient.get('first_name', 'Участник')
        last_name = recipient.get('last_name', '')
        stage_name = recipient.get('stage_name', 'новогодний квест')
        
        full_name = f"{first_name} {last_name}".strip()
        if not full_name:
            full_name = "Участник"
        
        subject = f"🎄 Добро пожаловать в Новогодний Квест, {first_name}!"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    text-align: center;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px 20px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 2px solid #eee;
                    color: #666;
                }}
                .stage-info {{
                    background: linear-gradient(135deg, #ffd89b, #19547b);
                    color: white;
                    padding: 15px;
                    border-radius: 10px;
                    margin: 20px 0;
                    text-align: center;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎄 Добро пожаловать в новогоднее приключение!</h1>
            </div>

            <p><strong>Здравствуйте, {first_name}!</strong></p>

            <p>Добро пожаловать в наше уникальное событие! Благодарим, что выбрали именно наш старт!</p>
            
            <p>Теперь Вы стали частью чего-то поистине волшебного — это не просто забег, а настоящее приключение, которое запомнится надолго!</p>

            <div class="stage-info">
                🎯 Этап: <strong>{stage_name}</strong>
            </div>

            <p>Скоро вы получите ссылку для начала квеста в Telegram. Следите за обновлениями!</p>

            <p><strong>Желаем незабываемых эмоций на старте!</strong></p>

            <div class="footer">
                <p>С любовью, команда «Стартани»! 💫</p>
                <p style="font-size: 12px; color: #999;">
                    Это автоматическое письмо, пожалуйста, не отвечайте на него.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Добро пожаловать в новогоднее приключение!

        Здравствуйте, {first_name}!

        Добро пожаловать в наше уникальное событие! Благодарим, что выбрали именно наш старт!

        Теперь Вы стали частью чего-то поистине волшебного — это не просто забег, а настоящее приключение, которое запомнится надолго!

        🎯 Этап: {stage_name}

        Скоро вы получите ссылку для начала квеста в Telegram. Следите за обновлениями!

        Желаем незабываемых эмоций на старте!

        С любовью, команда «Стартани»!

        ---
        Это автоматическое письмо, пожалуйста, не отвечайте на него.
        """
        
        return subject, html_content, text_content
    
    def completion_template(self, recipient: Dict[str, Any]) -> Tuple[str, str, str]:
        """Шаблон письма о завершении квеста"""
        first_name = recipient.get('first_name', 'Участник')
        stage_name = recipient.get('stage_name', 'новогодний квест')
        
        subject = f"🎉 Поздравляем с завершением Новогоднего Квеста, {first_name}!"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    text-align: center;
                    background: linear-gradient(135deg, #4ecdc4, #ff6b6b);
                    color: white;
                    padding: 30px 20px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 2px solid #eee;
                    color: #666;
                }}
                .celebration {{
                    text-align: center;
                    margin: 20px 0;
                }}
                .confetti {{
                    font-size: 24px;
                    margin: 10px;
                }}
                .results {{
                    background: #e8f5e8;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 20px 0;
                    border-left: 4px solid #4caf50;
                }}
                .stage-completion {{
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                    padding: 15px;
                    border-radius: 10px;
                    margin: 20px 0;
                    text-align: center;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎉 Поздравляем!</h1>
                <p>Вы успешно завершили Новогодний Квест!</p>
            </div>
            
            <div class="stage-completion">
                ✅ Этап "<strong>{stage_name}</strong>" завершен!
            </div>
            
            <div class="celebration">
                <span class="confetti">🎊</span>
                <span class="confetti">🎉</span>
                <span class="confetti">🏆</span>
                <span class="confetti">✨</span>
            </div>
            
            <h2>Ура, {first_name}!</h2>
            <p>Вы прошли все испытания и завершили этап "{stage_name}"! Это настоящее достижение! 🏆</p>
            
            <p>Благодарим вас за участие и проявленную настойчивость. Надеемся, что квест подарил вам:</p>
            <ul>
                <li>🎄 Настоящее новогоднее настроение</li>
                <li>🧩 Интересные задачи и головоломки</li>
                <li>🤝 Новые знания и навыки</li>
                <li>✨ Волшебные моменты и эмоции</li>
                <li>🎁 Возможность проявить себя</li>
            </ul>
            
            <div class="results">
                <h3 style="margin-top: 0; color: #2e7d32;">📊 Ваши результаты</h3>
                <p>Информация о результатах и возможных призах будет опубликована в ближайшее время. Следите за нашими сообщениями!</p>
            </div>
            
            <p>Хотите поделиться впечатлениями? Мы будем рады услышать ваши отзывы о квесте!</p>
            
            <p>С наступающим Новым Годом! Пусть следующий год будет полон таких же увлекательных приключений! 🎅✨</p>
            
            <p>С уважением и благодарностью,<br>
            <strong>Команда «Стартани»</strong></p>

            <div class="footer">
                <p>С любовью, команда «Стартани»! 💫</p>
                <p style="font-size: 12px; color: #999;">
                    Это автоматическое письмо, пожалуйста, не отвечайте на него.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Поздравляем с завершением Новогоднего Квеста!

        🎉 Ура, {first_name}!

        Вы успешно завершили этап "{stage_name}"! Это настоящее достижение!

        Благодарим вас за участие и проявленную настойчивость. 
        Надеемся, что квест подарил вам настоящее новогоднее настроение, 
        интересные задачи и волшебные моменты.

        📊 Ваши результаты:
        Информация о результатах и возможных призах будет опубликована 
        в ближайшее время. Следите за нашими сообщениями!

        Хотите поделиться впечатлениями? Мы будем рады услышать ваши отзывы о квесте!

        С наступающим Новым Годом! Пусть следующий год будет полон 
        таких же увлекательных приключений!

        С уважением и благодарностью,
        Команда «Стартани»

        ---
        Это автоматическое письмо, пожалуйста, не отвечайте на него.
        """
        
        return subject, html_content, text_content
    
    def test_template(self, recipient: Dict[str, Any]) -> Tuple[str, str, str]:
        """Тестовый шаблон"""
        subject = "🧪 Тестовое письмо - Новогодний Квест"
        stage_name = recipient.get('stage_name', 'тестовый этап')
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 20px; border-radius: 10px; margin-bottom: 30px;">
                    <h1>🧪 Тестовое письмо</h1>
                    <p>Новогодний Квест - Система рассылки</p>
                </div>
                
                <div style="background: linear-gradient(135deg, #ffd89b, #19547b); color: white; padding: 15px; border-radius: 10px; margin: 20px 0; text-align: center; font-weight: bold;">
                    🎯 <strong>{stage_name}</strong>
                </div>
                
                <p>Это тестовое письмо от системы рассылки Новогоднего Квеста.</p>
                <p><strong>Время отправки:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Получатель:</strong> {recipient.get('email', 'test@example.com')}</p>
                
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #667eea; margin-top: 0;">✅ Система работает корректно</h3>
                    <p>Если вы видите это письмо, значит система рассылки настроена правильно и готова к работе.</p>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background: #e7f3ff; padding: 20px; border-radius: 10px; display: inline-block;">
                        <p style="margin: 0; font-weight: bold; color: #0088cc;">🚀 Готовы к запуску новогоднего приключения!</p>
                    </div>
                </div>
                
                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 2px solid #eee; color: #666;">
                    <p>С любовью, команда «Стартани»! 💫</p>
                    <p style="font-size: 12px; color: #999;">
                        Это тестовое письмо, пожалуйста, не отвечайте на него.
                    </p>
                </div>
            </body>
        </html>
        """
        
        text_content = f"""
        Тестовое письмо - Новогодний Квест
        
        Это тестовое письмо от системы рассылки Новогоднего Квеста.
        
        🎯 Этап: {stage_name}
        
        Время отправки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        Получатель: {recipient.get('email', 'test@example.com')}
        
        ✅ СИСТЕМА РАБОТАЕТ КОРРЕКТНО
        Если вы видите это письмо, значит система рассылки настроена 
        правильно и готова к работе.
        
        🚀 Готовы к запуску новогоднего приключения!
        
        С любовью, команда «Стартани»!
        
        ---
        Это тестовое письмо, пожалуйста, не отвечайте на него.
        """
        
        return subject, html_content, text_content
