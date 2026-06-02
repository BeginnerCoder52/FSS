/*jshint esversion: 6 */
Module.register("MMM-Keyboard", {

  defaults: {
    showAlways: false,
    layout: "default",
    language: config.language || "en",
    startUppercase: true,
    startWithNumbers: false,
    debug: false,
  },

  layouts: {},

  VOWELS: 'aeiouyăâêôơưAEIOUYĂÂÊÔƠƯ',

  isVowel: function (ch) {
    return this.VOWELS.includes(ch);
  },

  isToneKey: function (ch) {
    return 'sfrxjSFRXJ'.includes(ch);
  },

  getVowelGroup: function (str) {
    var lastV = -1;
    for (var i = str.length - 1; i >= 0; i--) {
      if (this.isVowel(str[i])) { lastV = i; break; }
    }
    if (lastV === -1) return null;
    var start = lastV, end = lastV;
    while (start > 0 && this.isVowel(str[start - 1])) start--;
    while (end < str.length - 1 && this.isVowel(str[end + 1])) end++;
    if (start < end && start > 0) {
      if ((str[start] === 'u' || str[start] === 'U')
          && (str[start - 1] === 'q' || str[start - 1] === 'Q')) {
        start++;
      } else if ((str[start] === 'i' || str[start] === 'I')
          && (str[start - 1] === 'g' || str[start - 1] === 'G')) {
        start++;
      }
    }
    return { start: start, end: end, text: str.substring(start, end + 1) };
  },

  toneIdxInGroup: function (groupText, openSyllable) {
    var g = groupText.toLowerCase();
    var len = g.length;
    if (len >= 3 && /^(oay|uôi|ươi|ươu|uyế|uyệ|oăn)/.test(g)) return 2;
    if (len >= 2) {
      var last2 = g.substring(len - 2);
      if (/^(ai|ay|au|ao|oi|ôi|ơi|ui|ưi|eo|êu|iu|ưu|ia|ua|ưa)$/.test(last2)) return len - 2;
      if (openSyllable && /^(oa|oe)$/.test(last2)) return len - 2;
      if (/^(iê|uô|ươ|oa|oe|uy|uâ|uơ|oă|uya)$/.test(last2)) return len - 1;
    }
    return len - 1;
  },

  mergeOnTone: function (groupText) {
    var g = groupText.toLowerCase();
    if (g.length >= 2) {
      var pair = g.substring(0, 2);
      if (pair === 'uo') return { merged: 'uô', pos: 1 };
      if (pair === 'ie') return { merged: 'iê', pos: 1 };
    }
    if (g.length >= 3) {
      var triple = g.substring(0, 3);
      if (triple === 'uow') return { merged: 'ươ', pos: 1 };
      if (triple === 'uye') return { merged: 'uyê', pos: 2 };
    }
    return null;
  },

  applyTelex: function (raw) {
    var doubleMap = {
      'aa': 'â', 'ee': 'ê', 'oo': 'ô',
      'dd': 'đ',
      'AA': 'Â', 'EE': 'Ê', 'OO': 'Ô',
      'DD': 'Đ',
      'Aa': 'Â', 'Ee': 'Ê', 'Oo': 'Ô',
      'Dd': 'Đ', 'dD': 'Đ',
    };

    var vowelTones = {
      'a': { s:'á', f:'à', r:'ả', x:'ã', j:'ạ' },
      'ă': { s:'ắ', f:'ằ', r:'ẳ', x:'ẵ', j:'ặ' },
      'â': { s:'ấ', f:'ầ', r:'ẩ', x:'ẫ', j:'ậ' },
      'e': { s:'é', f:'è', r:'ẻ', x:'ẽ', j:'ẹ' },
      'ê': { s:'ế', f:'ề', r:'ể', x:'ễ', j:'ệ' },
      'i': { s:'í', f:'ì', r:'ỉ', x:'ĩ', j:'ị' },
      'o': { s:'ó', f:'ò', r:'ỏ', x:'õ', j:'ọ' },
      'ô': { s:'ố', f:'ồ', r:'ổ', x:'ỗ', j:'ộ' },
      'ơ': { s:'ớ', f:'ờ', r:'ở', x:'ỡ', j:'ợ' },
      'u': { s:'ú', f:'ù', r:'ủ', x:'ũ', j:'ụ' },
      'ư': { s:'ứ', f:'ừ', r:'ử', x:'ữ', j:'ự' },
      'y': { s:'ý', f:'ỳ', r:'ỷ', x:'ỹ', j:'ỵ' },
    };

    var toneRemoval = {
      'á':'a','à':'a','ả':'a','ã':'a','ạ':'a',
      'ắ':'ă','ằ':'ă','ẳ':'ă','ẵ':'ă','ặ':'ă',
      'ấ':'â','ầ':'â','ẩ':'â','ẫ':'â','ậ':'â',
      'é':'e','è':'e','ẻ':'e','ẽ':'e','ẹ':'e',
      'ế':'ê','ề':'ê','ể':'ê','ễ':'ê','ệ':'ê',
      'í':'i','ì':'i','ỉ':'i','ĩ':'i','ị':'i',
      'ó':'o','ò':'o','ỏ':'o','õ':'o','ọ':'o',
      'ố':'ô','ồ':'ô','ổ':'ô','ỗ':'ô','ộ':'ô',
      'ớ':'ơ','ờ':'ơ','ở':'ơ','ỡ':'ơ','ợ':'ơ',
      'ú':'u','ù':'u','ủ':'u','ũ':'u','ụ':'u',
      'ứ':'ư','ừ':'ư','ử':'ư','ữ':'ư','ự':'ư',
      'ý':'y','ỳ':'y','ỷ':'y','ỹ':'y','ỵ':'y',
      'Á':'A','À':'A','Ả':'A','Ã':'A','Ạ':'A',
      'Ắ':'Ă','Ằ':'Ă','Ẳ':'Ă','Ẵ':'Ă','Ặ':'Ă',
      'Ấ':'Â','Ầ':'Â','Ẩ':'Â','Ẫ':'Â','Ậ':'Â',
      'É':'E','È':'E','Ẻ':'E','Ẽ':'E','Ẹ':'E',
      'Ế':'Ê','Ề':'Ê','Ể':'Ê','Ễ':'Ê','Ệ':'Ê',
      'Í':'I','Ì':'I','Ỉ':'I','Ĩ':'I','Ị':'I',
      'Ó':'O','Ò':'O','Ỏ':'O','Õ':'O','Ọ':'O',
      'Ố':'Ô','Ồ':'Ô','Ổ':'Ô','Ỗ':'Ô','Ộ':'Ô',
      'Ớ':'Ơ','Ờ':'Ơ','Ở':'Ơ','Ỡ':'Ơ','Ợ':'Ơ',
      'Ú':'U','Ù':'U','Ủ':'U','Ũ':'U','Ụ':'U',
      'Ứ':'Ư','Ừ':'Ư','Ử':'Ư','Ữ':'Ư','Ự':'Ư',
      'Ý':'Y','Ỳ':'Y','Ỷ':'Y','Ỹ':'Y','Ỵ':'Y',
    };

    var result = '';
    var i = 0;
    while (i < raw.length) {
      var ch = raw[i];

      if ((ch === 'w' || ch === 'W') && result.length > 0) {
        var prev = result[result.length - 1];
        var lowerPrev = prev.toLowerCase();
        var wRep = null;
        if (lowerPrev === 'a') wRep = (prev === 'A') ? 'Ă' : 'ă';
        else if (lowerPrev === 'o') wRep = (prev === 'O') ? 'Ơ' : 'ơ';
        else if (lowerPrev === 'u') wRep = (prev === 'U') ? 'Ư' : 'ư';
        if (wRep) {
          result = result.substring(0, result.length - 1) + wRep;
          i++;
          continue;
        }
      }

      if (i + 1 < raw.length) {
        var pair = raw.substring(i, i + 2);
        var d = doubleMap[pair];
        if (d !== undefined) {
          if (!(i + 2 < raw.length && (raw[i + 2] === 'z' || raw[i + 2] === 'Z'))) {
            result += d;
            i += 2;
            continue;
          }
        }
      }

      if (this.isToneKey(ch) && result.length > 0
          && !(i + 1 < raw.length && this.isVowel(raw[i + 1]))) {
        var toneLower = ch.toLowerCase();
        var vg = this.getVowelGroup(result);

        if (vg) {
          var mergeInfo = this.mergeOnTone(vg.text);

          if (mergeInfo) {
            var merged = mergeInfo.merged;
            if (vg.text[0] === vg.text[0].toUpperCase() && vg.text[0] !== vg.text[0].toLowerCase()) {
              merged = merged[0].toUpperCase() + merged.slice(1);
            }
            var toneTarget = merged[mergeInfo.pos];
            var lowerTarget = toneTarget.toLowerCase();
            if (vowelTones[lowerTarget] && vowelTones[lowerTarget][toneLower]) {
              var accented = vowelTones[lowerTarget][toneLower];
              if (toneTarget !== lowerTarget) accented = accented.toUpperCase();
              merged = merged.substring(0, mergeInfo.pos) + accented + merged.substring(mergeInfo.pos + 1);
            }
            result = result.substring(0, vg.start) + merged
              + vg.text.substring(mergeInfo.merged.length)
              + result.substring(vg.end + 1);
            i++;
            continue;
          }

          var pos = this.toneIdxInGroup(vg.text, vg.end === result.length - 1);
          var toneIdx = vg.start + pos;
          var vowel = result[toneIdx];
          var lowerVowel = vowel.toLowerCase();
          if (vowelTones[lowerVowel] && vowelTones[lowerVowel][toneLower]) {
            var accented = vowelTones[lowerVowel][toneLower];
            if (vowel === vowel.toUpperCase() && vowel !== lowerVowel) {
              accented = accented.toUpperCase();
            }
            result = result.substring(0, toneIdx) + accented + result.substring(toneIdx + 1);
            i++;
            continue;
          }
        }

        result += ch;
        i++;
        continue;
      }

      if ((ch === 'z' || ch === 'Z') && result.length > 0) {
        var foundTone = false;
        for (var zj = result.length - 1; zj >= 0; zj--) {
          if (toneRemoval[result[zj]] !== undefined) {
            result = result.substring(0, zj) + toneRemoval[result[zj]] + result.substring(zj + 1);
            foundTone = true;
            break;
          }
        }
        i++;
        if (foundTone) continue;
      }

      result += ch;
      i++;
    }
    return result;
  },

  getStyles: function () {
    return [
      this.file('keyboard.css'),
      this.file('node_modules/simple-keyboard/build/css/index.css')
    ];
  },

  getScripts: function () {
    return [
      this.file('node_modules/simple-keyboard/build/index.js')
    ];
  },

  start: function () {
    this.shiftState = (this.config.startUppercase) ? 1 : 0;
    if (!["de", "en", "vi"].includes(this.config.language)) {
      this.config.language = "en";
    }
    this.loadLayouts();
  },

  loadLayouts: function() {
    this.log("Loading keyboard layouts");
    var xobj = new XMLHttpRequest();
    var self = this;
    xobj.overrideMimeType("application/json");
    xobj.open("GET", this.file('layouts.json'), true);
    xobj.onreadystatechange = function() {
      if (xobj.readyState === 4 && xobj.status === 200) {
        self.layouts = JSON.parse(xobj.responseText);
        self.log("Layouts loaded: " + self.layouts[self.config.language]);
        self.buildKeyboard();      
      }
    };
    xobj.send(null);
  },

  getDom: function () {
    var container = document.createElement("div");
    container.className = "keyboardWrapper";
    if (this.config.debug) {
      var kbButton = document.createElement("div");
      kbButton.width = "100px";
      kbButton.className = "kbButton fas fa-keyboard";
      kbButton.addEventListener("click", event => {
        this.showKeyboard();
        kbButton.style.display = "none";
      });
      container.appendChild(kbButton);
    }
    this.kbContainer = document.createElement("div");
    this.kbContainer.className = "kbContainer";
    var inputDiv = document.createElement("div");
    inputDiv.id = "inputDiv";
    inputDiv.style.display = "none";
    var input = document.createElement("input");
    input.id = "kbInput";
    input.setAttribute("type", "text");
    input.addEventListener("input", event => {
      this.keyboard.setInput(event.target.value);
    });
    var send = document.createElement("button");
    send.className = "sendButton";
    send.innerText = "  SEND!  ";
    send.setAttribute("name", "sendButton");
    send.onclick = () => {
      this.sendInput();
    };
    var hideButton = document.createElement("button");
    hideButton.className = "sendButton";
    hideButton.innerText = "\u21e7";
    hideButton.style.backgroundColor = "#880000";
    hideButton.setAttribute("name", "hideButton");
    hideButton.onclick = () => {
      this.hideKeyboard();
      document.getElementById("kbInput").value = '';
    };

    inputDiv.appendChild(input);
    inputDiv.appendChild(send);
    inputDiv.appendChild(hideButton);
    this.kbContainer.appendChild(inputDiv);
    var kb = document.createElement("div");
    kb.className = "simple-keyboard";
    this.kbContainer.appendChild(kb);
    container.appendChild(this.kbContainer);
    return container;
  },

  notificationReceived: function (noti, payload) {
    if (noti == "DOM_OBJECTS_CREATED") {
      this.log("MMM-Keyboard: Initializing keyboard");
      //Add event listener on first implementation of keyboard.
    } else if (noti == "KEYBOARD") {
      console.log("MMM-Keyboard recognized a notification: " + noti + JSON.stringify(payload));
      this.log("Activating Keyboard!");
      this.currentKey = payload.key;
      this.currentData = payload.data;
      var layout = (payload.style == "default") ? ((this.config.startUppercase) ? "shift" : "default") : "numbers";
      this.keyboard.setOptions({
        layoutName: layout
      });
      this.showKeyboard();
    }
  },

  sendInput: function () {
    var message = document.getElementById("kbInput").value;
    this.log("MMM-Keyboard sent input: " + message);
    this.sendNotification("KEYBOARD_INPUT", { key: this.currentKey, message: message, data: this.currentData});
    this.keyboard.clearInput();
    document.getElementById("kbInput").value = "";
    if (this.config.startUppercase) { this.shiftState = 1; } 
    this.hideKeyboard();
  },
  
  itemClicked: function (item) {
    this.sendSocketNotification("PURCHASED_ITEM", item);
  },


  onChange: function(input) {
    if (this._telexGuard) return;

    var displayValue = input;
    if (this.config.language === "vi") {
      var telexResult = this.applyTelex(input);
      if (telexResult !== input) {
        this._telexGuard = true;
        this.keyboard.setInput(telexResult);
        this._telexGuard = false;
      }
      displayValue = telexResult;
    }

    var kbInput = document.getElementById("kbInput");
    kbInput.value = displayValue;
    this.log("Input changed: " + displayValue);
    if (kbInput.value == "" && this.config.startUppercase) {
      this.shiftState = 1;
      this.handleShift();
    }

  },

  onKeyPress: function(button) {
    /**
     * Handles shift, lock and numbers buttons.
     */
    switch (button) {
      case "{shift}":
        this.shiftState = (this.shiftState === 0) ? 1 : (this.shiftState === 1) ? 2 : 0;
        this.handleShift(button);
        break;
      case "{lock}":
        this.shiftState = (this.shiftState < 2) ? 2 : 0;
        this.handleShift(button);
        break;
      case "{numbers}":
      case "{abc}":
        this.handleNumbers();
        break;
      case "{backspace}":
        if (document.getElementById("kbInput").value == "" && this.config.startUppercase) {
          this.shiftState = 1;
          this.handleShift(button)
        };
        break;
      default:
        this.shiftState = (this.shiftState < 2) ? 0 : 2;
        this.handleShift(button);
    }
  },

  handleShift: function(button) {
    var layout = (this.keyboard.options.layoutName == "numbers") ? "numbers" : (this.shiftState == 0) ? "default" : "shift";
    this.keyboard.setOptions({
      layoutName: layout
    });
    if (button == "{shift}") { this.log("Changing shift mode to " + layout); }
    this.showKeyboard();
  },

  handleNumbers: function() {
    var currentLayout = this.keyboard.options.layoutName;
    var numbersToggle = currentLayout !== "numbers" ? "numbers" : "default";
    this.keyboard.setOptions({
      layoutName: numbersToggle
    });
    this.showKeyboard();
  },


  buildKeyboard: function() {
    /*document.addEventListener("click", event => {
      if ( event.target !== this.keyboard.keyboardDOM && !event.target.classList.contains("keyboardWrapper") && !event.target.classList.contains("hg-button")) {
        this.hideKeyboard();
      }
    });*/
    var kbLayout = (this.config.startWithNumbers) ? "numbers" : (this.shiftState == 0) ? "default" : "shift";
    console.log(kbLayout);
    console.log(this.layouts);
    var Keyboard = window.SimpleKeyboard.default;
    this.keyboard = new Keyboard({
      onChange: input => this.onChange(input),
      onKeyPress: button => this.onKeyPress(button),
      mergeDisplay: true,
      inputName: "kbInput",
      layoutName: kbLayout,
      layout: this.layouts[this.config.language],
      buttonTheme: [
        {
          class: "specialButton",
          buttons: "{shift} {ent} {escape} {lock} {tab} {altleft} {altright} {abc} {numbers} {backspace} 0"
        },
        {
          class: "spaceButton",
          buttons: "{space}"
        },
        {
          class: "emptyButton",
          buttons: " "
        }
      ],
      display: {
        "{numbers}": "123",
        "{ent}": "return",
        "{escape}": "esc",
        "{tab}": "tab",
        "{backspace}": "  \u21e6  ",
        "{lock}": "  \u21ee  ",
        "{shift}": "  \u21e7  ",
        "{controlleft}": "ctrl",
        "{controlright}": "ctrl",
        "{altleft}": "alt",
        "{altright}": "alt",
        "{metaleft}": "cmd",
        "{metaright}": "cmd",
        "{abc}": "ABC"
      }
    });
  },

  showKeyboard: function() {
    this.kbContainer.classList.add("show-keyboard");
    document.getElementById("inputDiv").style.display = "block";
    document.getElementById("kbInput").value = this.keyboard.getInput();
  },

  hideKeyboard: function() {
    this.kbContainer.classList.remove("show-keyboard");
    if (this.config.debug) {
      document.getElementsByClassName("kbButton")[0].style.display = "block";
    }
  },

  log: function (msg) {
    if (this.config && this.config.debug) {
      console.log(this.name + ":", JSON.stringify(msg));
    }
  },

});
