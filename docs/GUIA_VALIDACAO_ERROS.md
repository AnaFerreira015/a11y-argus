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

**Como verificar:**
1. Calcule as dimensões: `(dir-esq)/2.625` e `(baixo-topo)/2.625`.
2. Confirme no XML que o elemento é interativo (`clickable="true"`).
3. Olhe o print: o elemento aparece **inteiro** ou está cortado pela borda
   da tela/rolagem?
4. Para o (Minimum): há outros elementos clicáveis encostados nele, ou ele
   está isolado (ex.: ícone sozinho numa barra espaçada)?

**É TP se:** a menor dimensão fica abaixo do limite, o elemento é um alvo de
toque real e, no caso do Minimum, há vizinhos próximos.
**É FP se:** o elemento está visivelmente **cortado** no print (o tamanho
real é maior; o argus mediu só a parte visível), ou é um container decorativo
tecnicamente clicável que não funciona como alvo (ex.: um layout de fundo).

**Armadilha:** elementos de largura total e baixinhos (barras) no rodapé:
confira se são mesmo interativos pro usuário ou só um container com
`clickable` herdado.

## 3. Missing Content Description / Missing Accessible Name (WCAG 1.1.1 / 4.1.2)

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

**[Opcional, comportamental]:** ative o TalkBack no emulador
(`adb shell settings put secure enabled_accessibility_services
com.google.android.marvin.talkback/com.google.android.marvin.talkback.TalkBackService`),
navegue até o elemento e ouça o que é anunciado. Use apenas em casos de
dúvida; desative depois
(`adb shell settings put secure enabled_accessibility_services ""`).

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

**Como verificar (30s):** olhe a região marcada no print com zoom. Algum
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

**A conta que resolve quase tudo (30s):** o próprio achado já traz as duas
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
| ~1.3 ou maior | O texto **escalou** (ou quebrou em mais linhas) | Isso **não deveria estar no report**; marque como FP e adicione comentário "razão X.XX, possível bug da ferramenta" |
| Entre ~1.0 e ~1.3 | Zona cinzenta (escalou só em parte) | Confirme no visual e descreva no comentário |

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
| ~0.85 ou menor | O texto **reduziu** corretamente | Não deveria estar no report; **FP** com comentário "razão X.XX, possível bug da ferramenta" |

Lembrete: este tipo **não é exigência da WCAG** (o achado já vem marcado
como Advisory); avalie normalmente e registre, a distinção já está nos dados.

---

## Varredura de FN (depois de validar os achados da ferramenta)

Com o print limpo da tela aberto, percorra esta lista; cada item que você
encontrar e que **não** está no `errors.json` vira uma linha de FN:

1. Algum texto visivelmente difícil de ler? (candidato a Contrast Failure)
2. Algum botão/ícone clicável minúsculo e apertado entre outros? (Target Size)
3. Algum ícone funcional que parece sem nome? Confira no XML. (Missing
   Content Description)
4. Algum campo de entrada sem rótulo nem hint? (Missing Label)
5. Compare rapidamente com o print large_text: algum texto claramente
   congelado? (Resize Text)

A varredura é o que dá validade à métrica de
recall; não pule.

## Quando parar

- Se um achado individual passar de 5 minutos sem conclusão, não force:
  marque a célula com comentário descrevendo a dúvida e siga. Casos ambíguos
  discutidos em conjunto valem mais que chutes consistentes.
- Registre no comentário qualquer medição que você fez (razão de contraste,
  dp calculado): isso transforma tua avaliação em evidência auditável.
