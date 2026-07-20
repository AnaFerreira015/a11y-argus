# Guia de validação por tipo de erro

Este guia ensina **como verificar** cada tipo de problema que o a11y-argus
reporta, antes de classificar como TP, FP ou FN na planilha. Ele complementa
o [MANUAL_EVALUATION.md](MANUAL_EVALUATION.md), que define a planilha e as
classificações; aqui está o "como conferir" de cada tipo, do jeito mais
rápido possível sem perder fidelidade.

## Princípio central: valide sobre os artefatos, não sobre o app ao vivo

Regra de ouro: **a verdade é a captura, não o emulador**. O argus analisou
uma tela específica, congelada nos arquivos:

- `output_dir_<apk>/results/result_<n>/output_images/` (achados marcados)
- `output_dir_<apk>/default/prints/` (screenshot limpo da tela)
- `output_dir_<apk>/default/xmls/` (hierarquia de UI da tela)
- `output_dir_<apk>/large_text/` e `small_text/` (mesma tela em outras escalas)

Se você reabrir o app no emulador, a tela pode estar diferente (conteúdo
dinâmico, datas, estados de sessão), e você estaria validando outra coisa.
Use o emulador apenas nos passos marcados como **[opcional, comportamental]**.

## Ferramentas (instalar uma vez)

1. **Conta-gotas de cor**: PowerToys Color Picker (Windows, `Win+Shift+C`)
   ou o conta-gotas do GIMP/Paint.NET. Para ler cores dos screenshots.
2. **Calculadora de contraste**: https://webaim.org/resources/contrastchecker/
   (cola as duas cores, ela devolve a razão e o veredito WCAG).
3. **Editor com busca**: VS Code, para abrir os XMLs e localizar elementos.

## Como localizar um elemento no XML pela posição

Vários tipos pedem conferência no XML. O caminho rápido:

1. Pegue os `bounds` do achado no `errors.json`, ex.: `[42, 712, 1038, 763]`.
2. Abra o `ui_dump_default_<screen_id>.xml` em `default/xmls/`.
3. Busque (Ctrl+F) por `[42,712` (o XML usa o formato `[esq,topo][dir,baixo]`
   sem espaços). O nó encontrado é o elemento do achado; os atributos
   (`text`, `content-desc`, `clickable`, `focusable`, `hint`, `class`) são o
   que você vai conferir.

## Conversão de pixels para dp

Os bounds estão em pixels; os critérios de tamanho da WCAG são em dp. No
nosso emulador (1080x2400, densidade 2.625):

```
dp = pixels / 2.625
```

Exemplo: um botão com bounds `[24, 1830, 108, 1914]` tem 84x84 px = **32x32dp**.
(Confirme a densidade do seu AVD uma vez com `adb shell wm density`: o valor
mostrado dividido por 160 é o fator; 420/160 = 2.625.)

---

## 1. Contrast Failure (WCAG 1.4.3)

**O que o critério exige:** texto legível contra o fundo. Razão mínima de
**4.5:1** para texto normal e **3:1** para texto grande (≥24dp, ou ≥18.7dp em
negrito).

**Como verificar:**
1. Localize o texto no print limpo (use a imagem anotada como guia de posição).
2. Com o conta-gotas, capture a cor do **miolo de uma letra** (evite as
   bordas, que têm anti-aliasing) e a cor do **fundo imediatamente ao lado**
   do texto.
3. Cole as duas no WebAIM Contrast Checker e leia a razão.
4. Compare com o threshold da mensagem do achado (o argus informa qual
   exigiu, 4.5 ou 3.0).

**É TP se:** a razão medida fica abaixo do threshold aplicável.
**É FP se:** a razão medida passa com folga (diferença clara da estimativa do
argus), ou a marcação não está sobre texto de verdade (área vazia, imagem).

**Armadilhas:**
- Texto sobre imagem ou gradiente: capture o fundo em mais de um ponto; se a
  razão falha em parte do texto, é falha real (a WCAG exige contraste em todo
  o texto).
- Divergência pequena (ex.: medido 4.4 vs exigido 4.5): ainda é falha; a
  tolerância é zero no critério. Anote a razão medida na coluna de observações.
- Texto grande vs normal: se a dúvida é qual threshold vale, meça a altura da
  letra maiúscula em px no print (zoom), converta pra dp e compare com 24dp.
  Na dúvida, anote e pergunte.

## 2. Target Size Failure / Target Size Failure (Minimum) (WCAG 2.5.5 / 2.5.8)

**O que os critérios exigem:** alvos de toque de pelo menos **44x44dp**
(2.5.5, nível AAA) ou **24x24dp** (2.5.8, nível AA). O 2.5.8 tem exceção:
alvo menor **passa** se estiver isolado (sem outros alvos encostados).
"Alvo" aqui significa **alvo de toque**: algo que responde ao toque
(`clickable="true"` ou `long-clickable="true"`). Um elemento apenas
`focusable="true"` (alcançável pelo leitor de tela, mas não tocável) **não
é** um alvo de toque e não deveria ser avaliado por este critério.

**Como verificar:**
1. Calcule as dimensões: `(dir-esq)/2.625` e `(baixo-topo)/2.625`.
2. Confirme no XML que o elemento é um **alvo de toque**: `clickable="true"`
   ou `long-clickable="true"`. Se ele for só `focusable="true"` com
   `clickable="false"`, é um rótulo/elemento focável, não um alvo: **FP**.
3. Olhe o print: o elemento aparece **inteiro** ou está cortado pela borda
   da tela/rolagem?
4. Para o (Minimum): há outros elementos clicáveis encostados nele, ou ele
   está isolado (ex.: ícone sozinho numa barra espaçada)?
5. Verifique o **alvo real**: se o elemento medido é um ícone/label pequeno
   **dentro** de um pai clicável maior (um item de lista, um card), quem
   recebe o toque é o pai. Meça o pai; se ele for grande o suficiente, é
   **FP** (o alvo de toque efetivo passa).

**É TP se:** a menor dimensão fica abaixo do limite, o elemento é um alvo de
toque real (não apenas focável) e, no caso do Minimum, há vizinhos próximos.
**É FP se:** o elemento é apenas focável e não clicável (não é alvo de
toque); ou está visivelmente **cortado** no print (o tamanho real é maior; o
argus mediu só a parte visível); ou é um container decorativo tecnicamente
clicável que não funciona como alvo (ex.: um layout de fundo); ou o alvo de
toque real é um ancestral maior que passa.

**Armadilha:** elementos de largura total e baixinhos (barras) no rodapé:
confira se são mesmo interativos pro usuário ou só um container com
`clickable` herdado.

## 3. Missing Content Description (WCAG 1.1.1)

**O que o critério exige:** todo elemento **funcional** não-textual (ícone,
imagem clicável, botão só com imagem) precisa de um nome acessível, que o
leitor de tela anuncia.

**Como verificar:**
1. Localize o elemento no print: ele faz algo quando tocado? (botão, ícone
   de ação, item de navegação)
2. No XML, confirme: `content-desc` vazio **e** `text` vazio.

**É TP se:** o elemento é funcional e não tem nem `content-desc` nem `text`.
**É FP se:** o elemento é puramente decorativo (enfeite, divisor, imagem
ilustrativa não clicável), ou o nome existe em outro atributo visível no XML.

**Relacionado:** o tipo **Missing Accessible Name** (seção 10) cobre a mesma
ideia para controles em geral; valide os dois pelo mesmo raciocínio, usando
sempre o `type` exato do achado.

## 4. Missing Label or Instruction (WCAG 3.3.2)

**O que o critério exige:** campos de entrada precisam de rótulo ou
instrução dizendo o que preencher.

**Como verificar:**
1. No print: existe um rótulo visível acima/ao lado do campo, ou um
   placeholder/hint dentro dele?
2. No XML: o nó tem `hint` ou `text` preenchido? Há um TextView de rótulo
   imediatamente acima?

**É TP se:** nada indica o que digitar (nem rótulo visível, nem hint).
**É FP se:** existe rótulo visível próximo, hint no campo, ou o contexto
torna a função inequívoca (ex.: campo único de busca com ícone de lupa).

## 5. Gesture-Only Navigation (WCAG 2.1.1)

**O que o critério exige:** toda funcionalidade operável por teclado. Um
elemento clicável que não recebe foco de entrada é inalcançável por teclado,
switch e d-pad.

**Como verificar:**
1. No XML, confirme o par: `clickable="true"` e `focusable="false"`.
2. Confirme no print que é um elemento com função real.

**É TP se:** o par se confirma e o elemento é interativo de verdade.
**É FP se:** o elemento é filho de uma ListView/AdapterView clássica (a
seleção é do container; o argus já deveria isentar, mas confira o ancestral
no XML), ou existe um "irmão" focável sobreposto que executa a mesma ação.

**[Opcional, comportamental]:** com o app aberto no emulador na mesma tela,
envie `adb shell input keyevent KEYCODE_TAB` repetidas vezes (ou setas com
KEYCODE_DPAD_DOWN) e observe se o foco visual alcança o elemento. Se o foco
pula o elemento, confirmação forte de TP.

## 6. Duplicate Text (WCAG 3.2.4)

**O que o critério exige:** componentes com a **mesma função** devem ser
identificados consistentemente; o problema é o inverso: mesmo texto para
funções **diferentes** confunde.

**Como verificar:** localize as ocorrências do texto no print. Elas
levam a ações/destinos diferentes?

**É TP se:** mesmo texto, funções diferentes (dois botões "OK" que fazem
coisas distintas na mesma tela).
**É FP se:** os textos repetidos são informativos (não interativos), ou são
itens de lista legitimamente iguais (ex.: "30 segundos" em duas
configurações distintas, cada uma com seu rótulo próprio).

## 7. Overlapping Elements (WCAG 1.4.12)

**O que o critério exige (na leitura do argus):** elementos que carregam
conteúdo (textos, e também ícones/controles com descrição) não devem se
sobrepor a ponto de prejudicar a leitura ou a compreensão do conteúdo. Na
prática a maioria dos casos envolve textos, mas um ícone invadindo um texto
(ou vice-versa) também conta.

**Como verificar:** olhe a região marcada no print com zoom. Algum
conteúdo fica ilegível, cortado ou encoberto pela sobreposição?

**É TP se:** a sobreposição prejudica visivelmente a leitura ou o uso de
algum dos elementos.
**É FP se:** os bounds se tocam no XML mas visualmente os conteúdos estão
íntegros (bounds maiores que o desenho real são comuns, especialmente em
elementos com padding), ou a sobreposição é intencional do design e sem
prejuízo (ex.: badge de notificação sobre o canto de um ícone).

## 8. Resize Text - insufficient increase (WCAG 1.4.4)

**O que o critério exige:** o texto deve responder à preferência de tamanho
de fonte do usuário. A falha típica é texto que **fica do mesmo tamanho**
quando o usuário aumenta a fonte (tamanho fixo em dp em vez de sp).

**A conta que resolve quase tudo:** o próprio achado já traz as duas
medidas. No `errors.json`, pegue `original_height` (altura na tela normal) e
`new_height` (altura na tela com fonte grande) e divida:

```
razão = new_height / original_height
```

A captura com fonte grande usa escala 1.3, então um texto que escala
corretamente fica ~1.3x mais alto. Como ler a razão:

| Razão | Significado | O que fazer |
|---|---|---|
| ~1.0 (ex.: 51/51) | O texto **ignorou** o aumento de fonte | Provável **TP**; confirme no visual (passo abaixo) |
| ~1.3 ou maior | O texto **escalou** (ou quebrou em mais linhas) | Isso **não deveria estar no report**; marque como FP |
| Entre ~1.0 e ~1.3 | Zona cinzenta (escalou só em parte) | Confirme no visual |

**Confirmação visual:** abra lado a lado o print da tela em
`default/prints/` e o da **mesma tela** em `large_text/prints/` (mesmo
screen_id no nome, prefixo da pasta diferente) e olhe o texto apontado.
O que a conta disse deve bater com o que você vê.

**É TP se:** razão ~1.0 e, no visual, o texto está do mesmo tamanho nas duas
capturas.
**É FP se:** o texto cresceu visivelmente (quebrar em mais linhas também
conta como crescer: é evidência de que escalou).

**Armadilha:** no visual, compare o **mesmo elemento** nas duas imagens;
listas podem ter rolado diferente entre as capturas. Use textos vizinhos
como âncora.

## 9. Resize Text - insufficient reduction

Mesma lógica do item 8, no sentido contrário: a captura pequena usa escala
0.85, então texto que responde corretamente fica ~0.85x da altura (ou seja,
**menor**). Divida `new_height / original_height`:

| Razão | Significado | O que fazer |
|---|---|---|
| ~1.0 | O texto **ignorou** a redução de fonte | Provável **TP**; confirme comparando `default/prints/` com `small_text/prints/` |
| ~0.85 ou menor | O texto **reduziu** corretamente | Não deveria estar no report; **FP** |

Lembrete: este tipo **não é exigência da WCAG** (o achado já vem marcado
como Advisory); avalie normalmente e registre, a distinção já está nos dados.

## 10. Missing Accessible Name (WCAG 4.1.2)

**O que o critério exige:** todo componente de interface (botão, campo,
controle) precisa de um nome acessível que identifique sua função para
tecnologias assistivas. É parecido com o item 3, mas aqui o foco é em
**controles interativos** (não só imagens/ícones): um botão sem texto nem
descrição, um campo sem rótulo programático.

**Como verificar:**
1. Localize o elemento no print: é um controle com função (botão, campo,
   switch, aba)?
2. No XML, confirme que não há `text` nem `content-desc`, e que nenhum
   rótulo programático o nomeia.

**É TP se:** o controle é interativo e não tem nome acessível nenhum.
**É FP se:** o nome existe em algum atributo (text, content-desc), ou o
elemento não é um controle que precise ser anunciado.

**Diferença para o item 3 (Missing Content Description):** na prática os dois
se sobrepõem; use o `type` exato do achado no `errors.json` para saber qual
foi reportado, e valide pelo mesmo raciocínio (o elemento é funcional e está
sem nome?).

## 11. Non-essential Content Description Should Be Empty (WCAG 1.1.1)

**O que o critério exige:** o **inverso** do item 3. Elementos puramente
**decorativos** (que não fazem nada e não transmitem informação) devem ter
descrição **vazia**, para que o leitor de tela os pule. Descrição em um
enfeite vira ruído: o usuário de leitor de tela ouve algo que não importa.

**Como verificar:**
1. Localize o elemento no print: ele é decorativo? (divisor, fundo, ícone
   ilustrativo que não faz nada ao tocar, imagem de enfeite)
2. No XML, confirme que ele **tem** `content-desc` preenchido apesar de ser
   decorativo.

**É TP se:** o elemento é decorativo e carrega uma descrição desnecessária.
**É FP se:** o elemento na verdade tem função (é clicável) ou transmite
informação real (então a descrição é correta e necessária).

## 12. Focus Order Failure (WCAG 2.4.3)

**O que o critério exige:** a ordem em que o foco percorre os elementos deve
preservar o sentido, tipicamente seguindo a ordem visual de leitura (de cima
para baixo, da esquerda para a direita).

**Como verificar:** o achado aponta um elemento cuja posição na ordem de foco
diverge da posição visual esperada. No print, avalie: se o foco chegasse
nesse elemento naquele ponto da sequência, o fluxo ficaria confuso (ex.: o
foco salta do topo direto para o rodapé e depois volta para o meio)?

**É TP se:** a divergência quebra o fluxo lógico de navegação.
**É FP se:** a ordem diferente da visual ainda faz sentido de uso (ex.:
agrupamentos legítimos, como percorrer todos os campos de um formulário antes
dos botões fixos no topo).

**[Opcional, comportamental]:** com a tela aberta no emulador, percorra com
`adb shell input keyevent KEYCODE_TAB` (ou KEYCODE_DPAD_DOWN) e observe a
sequência real do foco. É a confirmação mais forte para este tipo.

**Atenção:** este é um dos tipos com maior tendência a falso positivo (a
ordem "correta" muitas vezes é questão de julgamento). Na dúvida, marque com
comentário em vez de forçar TP/FP, e discuta os casos em conjunto.

## 13. Link Purpose Failure (WCAG 2.4.4)

**O que o critério exige:** o propósito de cada link ou ação deve ser
compreensível pelo próprio rótulo ou pelo contexto imediato. Rótulos
genéricos como "clique aqui", "saiba mais", "ver mais", sozinhos, não dizem
para onde levam.

**Como verificar:** olhe o elemento no print. Lendo **apenas o rótulo
dele**, dá para saber o que acontece ao tocar? Se não, existe texto
imediatamente ao lado que complete o sentido?

**É TP se:** o rótulo é genérico e o contexto próximo não resolve (ex.: três
botões "Saiba mais" na mesma tela, cada um levando a um destino diferente).
**É FP se:** o contexto imediato torna o destino inequívoco (ex.: um card com
título "Plano Premium" e, dentro dele, o botão "Saiba mais").

## 14. Missing Error Description (WCAG 3.3.1)

**O que o critério exige:** quando um campo entra em estado de erro, o erro
deve ser identificado e descrito em texto para o usuário.

**Como este check funciona (contexto importante):** o argus detecta o estado
de erro por sinais estruturais e de `resource-id` (um texto colado abaixo do
campo cujo id indica erro, como `til_error`), de forma independente de idioma.
Ele **não** usa o `errorText` do sistema (que não aparece no dump XML), então
a cobertura deste critério é parcial e conservadora: ele só dispara quando há
sinalização estrutural clara de erro.

**Como verificar:** localize o campo apontado no print. Há um indício visual
de erro (borda vermelha, ícone de alerta) mas **sem** texto explicando o
problema ao lado/abaixo?

**É TP se:** o campo está claramente em estado de erro e não há descrição
textual do erro.
**É FP se:** existe uma mensagem de erro em texto que o argus não associou ao
campo, ou o campo não está de fato em estado de erro (a sinalização que
disparou o achado era outra coisa).

**Observação:** por ser um check conservador, este tipo tende a ser raro nos
resultados. Casos de campos em erro sem descrição que o argus **não** pegou
devem entrar como FN na varredura.

---

## Varredura de FN (depois de validar os achados da ferramenta)

Com o print limpo da tela aberto, percorra esta lista; cada item que você
encontrar e que **não** está no `errors.json` vira uma linha de FN:

1. Algum texto visivelmente difícil de ler? (candidato a Contrast Failure)
2. Algum botão/ícone clicável minúsculo e apertado entre outros? (Target Size)
3. Algum ícone/controle funcional que parece sem nome? Confira no XML.
   (Missing Content Description / Missing Accessible Name)
4. Algum campo de entrada sem rótulo nem hint? (Missing Label)
5. Compare rapidamente com o print large_text: algum texto claramente
   congelado? (Resize Text)
6. Algum link/botão com rótulo genérico ("saiba mais", "clique aqui") sem
   contexto que esclareça? (Link Purpose)
7. Algum campo claramente em erro (borda vermelha, alerta) sem texto
   explicando o problema? (Missing Error Description)

A varredura leva 2-3 minutos por tela e é o que dá validade à métrica de
recall; não pule.

## Quando parar

- Meta: **5 a 10 minutos por tela** (validação dos achados + varredura).
- Se um achado individual passar de 5 minutos sem conclusão, não force:
  marque a célula com comentário descrevendo a dúvida e siga. Casos ambíguos
  discutidos em conjunto valem mais que chutes consistentes.