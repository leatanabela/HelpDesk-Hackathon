from collections.abc import AsyncGenerator #inseamna ca a doua functie returneaza un generator asincron, adica poate "cedeaza" (yield) bucati de text pe masura ce sunt generate, fara a astepta sa se termine totul
import ollama
from ai.config import settings
#interfata de comunicare intre back si ai

#
#Definești funcția care primește întrebarea ta (prompt) și, opțional, instrucțiunile de sistem (system_prompt)
# . La final, returnează un singur text lung (str).
def generate_response(prompt: str, system_prompt: str | None = None) -> str:
    """
    Generează un răspuns complet (sincron) folosind modelul configurat în Ollama.
    Așteaptă ca întregul text să fie generat înainte de a-l returna.
    """
    # construim istoriul de mesaje

    messages = []
    
    # oferim ai ului promptul sau
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # Adăugăm întrebarea sau instrucțiunea utilizatorului
    messages.append({"role": "user", "content": prompt})

    # Apelează serverul
    response = ollama.chat(
        model=settings.LLM_MODEL,
        messages=messages,
    )
    
    # Returnează doar conținutul textual al mesajului primit
    return response["message"]["content"]

#functia de afisare a raspunsului in flux (streaming/asincron) pentru a nu crede utilizatorul ca aplicatia a inghetat,
#  ci sa vada cum raspunsul se construieste pe masura ce e generat
async def generate_response_stream(
    prompt: str, system_prompt: str | None = None
) -> AsyncGenerator[str, None]:
    """
    Generează un răspuns în flux (streaming/asincron).
    Returnează bucăți de text pe măsură ce sunt generate de model.
    """
    messages = []
    
    # Configurarea contextului (similar cu funcția de mai sus)
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Apelează API-ul cu parametrul stream=True
    # Aceasta returnează un obiect iterabil, nu un răspuns final
    stream = ollama.chat(
        model=settings.LLM_MODEL,
        messages=messages,
        stream=True,#ii zie serverului sa nu astepte sa genereze tot raspunsul, ci sa ne trimita bucati de text pe masura ce sunt gata
    )

    # Parcurgem fiecare "chunk" (bucățică) primită de la server
    for chunk in stream:
        content = chunk["message"]["content"] #Desfacem pachețelul și extragem doar literele/cuvintele noi.
        if content:
            # yield spune: „Ține bucățica asta și afișeaz-o, dar nu pleca, mai am de trimis!”.
            yield content

            #bfhsbhbsjhf