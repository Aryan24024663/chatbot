Requirements:
- Ollama from the ollama website
    - in your CMD / command line run the command " ollama " to see if its downloaded into your system
      or just open the ollama application. Once you know its downloaded then run the command "ollama pull gemma:2b"
      this will download the model "Gemma:2b" to your local machine, its a model based on Googles gemini. It its 
      only 1.7 GB unlike the other models so it doesnt take up that much storage.
    - To make sure its downloaded run "ollama list" and you should see "Gemma:2b"

- In VS Code: open the files from the one drive.

- If you want to edit it then upload your new edited version with a name like "chatbot_your-name_1" or "chatbot_your-name_2" etc
  And also add in your own READ.ME.txt file explaining what you added / fixed / whatever, just so we can see whos contributed what they did.


Just copy and paste the code in


you might need to install flask, langchain and langchain_ollama to get shit to start working.
- Do this by the command "pip install x"
  - X = langchain or flask or langchain_ollama

create your files in this structre (Flask wont run otherwise)
- Static
  - JavaScript (js)
  - Stylesheet (css)
- Templates
  - HTML file
chatbot python file
flask app