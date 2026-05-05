JAARK Support Chatbot README

This is a local Flask chatbot that answers questions using the provided
documents and references. It uses Ollama with the gemma:7b model.


Requirements
------------

1. Install Ollama from the Ollama website.

2. Check that Ollama works by running:

   ollama

3. Download the model used by the chatbot:

   ollama pull gemma:7b

4. Check that the model is installed:

   ollama list

   You should see gemma:7b in the list.

5. Install the Python packages:

   pip install -r requirements.txt

   The requirements file includes:

   - flask
   - langchain
   - langchain_ollama
   - pypdf
   - python-docx
   - Pillow
   - pytesseract

6. Optional: install Tesseract OCR if you want the chatbot to read text from
   images inside PDFs.

   If Tesseract is not installed, the chatbot will still work, but OCR text
   from image-based PDFs may not be available.


How To Run
----------

From the main project folder, run:

   python3 chatbot/app.py

Then open this address in your browser:

   http://127.0.0.1:5000

The chatbot page is available at:

   http://127.0.0.1:5000/chatbot


Project Structure
-----------------

The Flask app expects this structure:

   chatbot/
   - app.py
   - chatbot.py
   - requirements.txt
   - READ_ME.txt
   - documents/
   - static/
   - templates/


Documents
---------

Put reference documents inside the documents folder:

   chatbot/documents/

The chatbot currently supports:

   - PDF files (.pdf)
   - Word documents (.docx)

It also checks for PDF and Word files directly inside the chatbot folder.


How The Chatbot Answers
-----------------------

When a user asks a question, the chatbot:

1. Loads the provided PDF and Word documents.
2. Extracts the text from those documents.
3. Splits long documents into smaller chunks.
4. Compares the question with the document chunks.
5. Selects the most relevant document section.
6. Answers using only the provided reference material.
7. Adds a source reference at the end of the answer when possible.

Example answer format:

   The answer from the document goes here.

   Source: example.pdf | Page 2

If the answer is not clearly found in the documents, the chatbot should reply:

   I can only answer questions using the provided documents and references.


Notes
-----

- The chatbot is designed to avoid using outside knowledge.
- Simple messages like hello, thanks, ok, and bye are handled with friendly
  preset responses.
- If port 5000 is already in use, stop the old Flask process or change the port
  in app.py.
- Keep any new project notes clear so other contributors can understand what
  changed.
