
var confirmElement = document.querySelector(".confirm");

function closePage(){
  clearClassList();
}

function openPage(page){
  clearClassList();
  var classList = confirmElement.classList;
  classList.add("page_open");
  classList.add("page_" + page + "_open");
}

function clearClassList(){
  var classList = confirmElement.classList;
  classList.remove("page_open");
  classList.remove("page_1_open");
  classList.remove("page_2_open");
  classList.remove("page_3_open");
}

var time = document.getElementById("time");
var options = { year: 'numeric', month: 'numeric', day: '2-digit' };
var optionsTime = { second: 'numeric', minute: 'numeric', hour: '2-digit' };

if (localStorage.getItem("update") == null){
  localStorage.setItem("update", "21.05.2025")
}

var date = new Date();

var updateText = document.querySelector(".bottom_update_value");
updateText.innerHTML = localStorage.getItem("update");

var update = document.querySelector(".update");
update.addEventListener('click', () => {
  var newDate = date.toLocaleDateString("pl-PL", options);
  localStorage.setItem("update", newDate);
  updateText.innerHTML = newDate;

  scroll(0, 0)
});

function delay(time) {
    return new Promise(resolve => setTimeout(resolve, time));
}

setClock();
function setClock(){
    date = new Date();
    time.innerHTML = "Czas: " + date.toLocaleTimeString("pl-PL", optionsTime) + " " + date.toLocaleDateString("pl-PL", options);    
    delay(1000).then(() => {
        setClock();
    })
}

var unfold = document.querySelector(".info_holder");
unfold.addEventListener('click', () => {

  if (unfold.classList.contains("unfolded")){
    unfold.classList.remove("unfolded");
  }else{
    unfold.classList.add("unfolded");
  }

})

var data = {}

// Get doc_id from URL
var params = new URLSearchParams(window.location.search);
var docId = params.get('doc_id');

// Try to get data from sessionStorage first (from secure server-side storage)
var docData = sessionStorage.getItem('document_data');
if (docData) {
  try {
    data = JSON.parse(docData);
  } catch (e) {
    console.error('Error parsing document data:', e);
  }
}

// If no data in sessionStorage but we have doc_id, fetch from server
if (Object.keys(data).length === 0 && docId) {
  // Synchronous fetch - we'll use async and wait
  fetch(`/api/documents/${docId}`)
    .then(response => response.json())
    .then(serverData => {
      data = serverData;
      // Store it for future use
      sessionStorage.setItem('document_data', JSON.stringify(data));
      // Re-render with fetched data
      refreshCardData();
    })
    .catch(error => {
      console.error('Error fetching document:', error);
    });
}

// Fallback to URL parameters (old method) if still no data
if (Object.keys(data).length === 0) {
  for (var key of params.keys()){
    if (key !== 'doc_id') {
      data[key] = params.get(key);
    }
  }
}

function refreshCardData() {
  // Set image
  if (data['image']) {
    document.querySelector(".id_own_image").style.backgroundImage = `url(${data['image']})`;
  }

  // Parse birthday
  var birthday = data['birthday'];
  if (!birthday) {
    birthday = "01.01.2000";
  }

  var birthdaySplit = birthday.split(".");
  var day = parseInt(birthdaySplit[0]) || 1;
  var month = parseInt(birthdaySplit[1]) || 1;
  var year = parseInt(birthdaySplit[2]) || 2000;

  var birthdayDate = new Date();
  birthdayDate.setDate(day)
  birthdayDate.setMonth(month-1)
  birthdayDate.setFullYear(year)

  birthday = birthdayDate.toLocaleDateString("pl-PL", options);

  var sex = data['sex'];

  if (sex === "m"){
    sex = "Mężczyzna"
  }else if (sex === "k"){
    sex = "Kobieta"
  }

  setData("name", (data['name'] || "").toUpperCase());
  setData("surname", (data['surname'] || "").toUpperCase());
  setData("nationality", (data['nationality'] || "").toUpperCase());
  setData("birthday", birthday);
  setData("familyName", data['familyName'] || "");
  setData("sex", sex);
  setData("fathersFamilyName", data['fathersFamilyName'] || "");
  setData("mothersFamilyName", data['mothersFamilyName'] || "");
  setData("birthPlace", data['birthPlace'] || "");
  setData("countryOfBirth", data['countryOfBirth'] || "");
  setData("adress", "ul. " + (data['adress1'] || "") + "<br>" + (data['adress2'] || "") + " " + (data['city'] || ""));

  if (localStorage.getItem("homeDate") == null){
    var homeDay = getRandom(1, 25);
    var homeMonth = getRandom(0, 12);
    var homeYear = getRandom(2012, 2019);

    var homeDate = new Date();
    homeDate.setDate(homeDay);
    homeDate.setMonth(homeMonth);
    homeDate.setFullYear(homeYear)

    localStorage.setItem("homeDate", homeDate.toLocaleDateString("pl-PL", options))
  }

  document.querySelector(".home_date").innerHTML = localStorage.getItem("homeDate")

  if (parseInt(year) >= 2000){
    month = 20 + month;
  }

  var later;

  if (sex.toLowerCase() === "mężczyzna"){
    later = "0295"
  }else{
    later = "0382"
  }

  if (day < 10){
    day = "0" + day
  }

  if (month < 10){
    month = "0" + month
  }

  // Use PESEL from data if available, otherwise generate it
  var pesel = data['pesel'];
  if (!pesel || pesel === 'undefined') {
    pesel = year.toString().substring(2) + month + day + later + "7";
  }
  setData("pesel", pesel);
}

// Call immediately if data is available
if (Object.keys(data).length > 0) {
  refreshCardData();
}

function setData(id, value){

  document.getElementById(id).innerHTML = value;

}

function getRandom(min, max) {
  return parseInt(Math.random() * (max - min) + min);
}

// Activate bottom nav tab from query param ?tab=home|services|qr|more
(function(){
  try{
    var tab = (new URLSearchParams(window.location.search).get('tab')||'home').toLowerCase();
    var valid = ['home','services','qr','more'];
    if (!valid.includes(tab)) tab = 'home';
    var imgs = document.querySelectorAll('.bottom_element_image');
    var texts = document.querySelectorAll('.bottom_element_text');
    var openClasses = ['home_open','services_open','qr_open','more_open'];
    imgs.forEach(function(img){ openClasses.forEach(c=>img.classList.remove(c)); });
    texts.forEach(function(t){ t.classList.remove('open'); });
    document.querySelectorAll('.bottom_element_grid').forEach(function(el){
      var send = el.getAttribute('send');
      var img = el.querySelector('.bottom_element_image');
      var txt = el.querySelector('.bottom_element_text');
      if (send===tab){ if(img) img.classList.add(tab+'_open'); if(txt) txt.classList.add('open'); }
    });
  }catch(e){}
})();
