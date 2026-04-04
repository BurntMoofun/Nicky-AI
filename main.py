import sys
from chatbot import Chatbot

if __name__ == "__main__":
    chatbot = Chatbot()
    if "--gui" in sys.argv:
        from gui import NickyGUI
        NickyGUI(chatbot).run()
    else:
        chatbot.chat()
    sys.exit(0)
