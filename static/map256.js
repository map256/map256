var markers = new Array();
var lines = new Array();
var infowindows = new Array();
var markers_visible = false;
var gradient_visible = false;
var marker_position = 0;

function hex (c) {
	var s = "0123456789abcdef";
	var i = parseInt (c);
	if (i == 0 || isNaN (c))
		return "00";
	i = Math.round (Math.min (Math.max (0, i), 255));
	return s.charAt ((i - i % 16) / 16) + s.charAt (i % 16);
}

function convertToHex (rgb) {
	return hex(rgb[0]) + hex(rgb[1]) + hex(rgb[2]);
}

function trim (s) { 
	return (s.charAt(0) == '#') ? s.substring(1, 7) : s 
}

function convertToRGB (hex) {
	var color = [];
	color[0] = parseInt ((trim(hex)).substring (0, 2), 16);
	color[1] = parseInt ((trim(hex)).substring (2, 4), 16);
	color[2] = parseInt ((trim(hex)).substring (4, 6), 16);
	return color;
}

function toggle_markers() {
	if ( markers_visible == false ) {
		for (var x in markers) {
			markers[x].setVisible(true);
		}
		markers_visible = true;
	} else {
		for (var x in markers) {
			markers[x].setVisible(false);
		}
		markers_visible = false;
	}
}

function toggle_gradient() {
	var start_col = convertToRGB('#FF0000');
	var end_col = convertToRGB('#0000FF');
	var alpha = 0.5;
	var cur_col = '#FF0000';

	if ( gradient_visible == false ) {
		for (var x = 0; x < lines.length; x++) {
			var c = [];
			var tmp_a = 1 - (x / (lines.length - 1));
			c[0] = start_col[0] * tmp_a + (1 - tmp_a) * end_col[0];
			c[1] = start_col[1] * tmp_a + (1 - tmp_a) * end_col[1];
			c[2] = start_col[2] * tmp_a + (1 - tmp_a) * end_col[2];
			cur_col = '#' + convertToHex(c);
			lines[x].setOptions({ strokeColor: cur_col});
		}

		gradient_visible = true;
	} else {
		for (var x = 0; x < lines.length; x++) {
			lines[x].setOptions({ strokeColor: '#000000'});
		}

		gradient_visible = false;
	}
}

function goto_latest() {
	markers[marker_position].setVisible(false);
	marker_position = 0;
	markers[marker_position].setVisible(true);
}

function goto_previous() {
	markers[marker_position].setVisible(false);

	if (marker_position < (markers.length-2) ) {
		marker_position = marker_position + 1;
	} else {
		marker_position = markers.length - 1;
	}

	markers[marker_position].setVisible(true);
}

function goto_next() {
	markers[marker_position].setVisible(false);

	if (marker_position == 0) {
		marker_position = 0;
	} else {
		marker_position = marker_position - 1;
	}

	markers[marker_position].setVisible(true);
}

function goto_earliest() {
	markers[marker_position].setVisible(false);
	marker_position = markers.length - 1;
	markers[marker_position].setVisible(true);
}

function initialize() {
	var mapOptions = {
		zoom: 12,
		center: centerpt,
		mapTypeId: google.maps.MapTypeId.ROADMAP
	};

	var map = new google.maps.Map(document.getElementById("map_canvas"), mapOptions);

	for (var i=1; i<=checkinPath.length; i++) {
		if (checkinPath[i-1] != checkinPath[i]) {
			lines.push(new google.maps.Polyline({
				path: new Array(checkinPath[i-1], checkinPath[i]),
				strokeColor: "#000000",
				strokeOpacity: 1.0,
				strokeWeight: 2
			}));
		}
	}

	for (var y in checkinPath) {
		markers.push(new google.maps.Marker({
			position: checkinPath[y],
			map: map,
			visible: false
		}));
	}

	for (var x in lines) {
		lines[x].setMap(map);
	}

	google.maps.event.addDomListener(document.getElementById("g_n"), "click", function(ev) {
		map.setCenter(markers[marker_position].getPosition());
	});

	google.maps.event.addDomListener(document.getElementById("g_l"), "click", function(ev) {
		map.setCenter(markers[marker_position].getPosition());
	});

	google.maps.event.addDomListener(document.getElementById("g_p"), "click", function(ev) {
		map.setCenter(markers[marker_position].getPosition());
	});

	google.maps.event.addDomListener(document.getElementById("g_e"), "click", function(ev) {
		map.setCenter(markers[marker_position].getPosition());
	});
}

function createMarker(marker, infowindow, map) {
	google.maps.event.addListener(marker, 'click', function() {
		infowindow.open(map, marker);
	})
}

function initialize_front() {
	var mapOptions = {
		zoom: 4,
		center: new google.maps.LatLng(37.9523113,-91.7715052),
		mapTypeId: google.maps.MapTypeId.ROADMAP
	};

	var map = new google.maps.Map(document.getElementById("map_canvas"), mapOptions);
	var blarg = new Array();

	for (key in blob2) {
		var path = new Array();

		for (var item in blob2[key]) {
			var foo = blob2[key][item].split(",");
			path.push(new google.maps.LatLng(foo[0], foo[1]));
		}

		lines.push(new google.maps.Polyline({
			path: path,
			strokeColor: "#FF0000",
			strokeOpacity: 1.0,
			strokeWeight: 4,
			map: map
		}));
		
		var bar = blob2[key][0].split(",");

		markers[key] = new google.maps.Marker({
			position: new google.maps.LatLng(bar[0], bar[1]),
			map: map,
			title: key
		});
		
		infowindows[key] = new google.maps.InfoWindow({
			content: "<h1>"+key+"</h1>"+"<a href=\"/t/"+key+"\">See the map for this person</a>",
			maxWidth: 200
		});
	}

	for (var key2 in markers) {
		createMarker(markers[key2], infowindows[key2], map);
	}
}
