var map;
var users = new Object();

function createMarker(marker, infowindow) {
	google.maps.event.addListener(marker, 'click', function() {
		infowindow.open(map, marker);
	})
}

function add_user_to_map(user_key, point_data, line_color) {
    users[user_key] = 1;
    var path = new Array();
    var markers = new Array();
    var infowindows = new Array();

    for (var key in point_data) {
        var geodata = point_data[key].split(',');
        path.push(new google.maps.LatLng(geodata[0], geodata[1]));
    }

    users[user_key]['line'] = new google.maps.Polyline({
        path: path,
        strokeColor: line_color,
        strokeOpacity: 1.0,
        strokeWeight: 4,
        map: map
    });

    var first_point = point_data[0].split(',');

    markers.push(new google.maps.Marker({
		position: new google.maps.LatLng(first_point[0], first_point[1]),
		map: map,
		title: user_key
	}));

    users[user_key]['markers'] = markers;

	infowindows.push(new google.maps.InfoWindow({
		content: "<h4><a href=\"/f/"+user_key+"\">"+user_key+"</a></h4>",
		maxWidth: 200
	}));
	
	users[user_key]['infowindows'] = infowindows;

    for (var key in markers) {
	    createMarker(markers[key], infowindows[key]);
    }
}

function add_front_page_data(retrieved_data) {
    for (var key in retrieved_data) {
        add_user_to_map(key, retrieved_data[key], '#FF0000');
    }
}

function change_page_type (target_type) {
    //Clear page

    if (target_type == 'frontpage') {
        $.getJSON('/front_page_data', function(data) { add_front_page_data(data); })
    }
}

function initialize_page () {
    var mapOptions = {
        zoom: 4,
        center: new google.maps.LatLng(37.958135,-91.773429),
        mapTypeId: google.maps.MapTypeId.ROADMAP
    };

    map = new google.maps.Map(document.getElementById("map_canvas"), mapOptions);

    // Check for URL contents here
    change_page_type('frontpage');
}

/* --------------------- OLD AND BAD BELOW THIS LINE ---------------------- */

var markers = new Array();
var lines = new Array();
var infowindows = new Array();
var markers_visible = false;
var gradient_visible = false;
var marker_position = 0;
var centerpt = new google.maps.LatLng(37.958135,-91.773429);
var map;

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

function setvalue(event, ui) {
	var valx = $("#slider").slider( "option", "value" );
	markers[marker_position].setVisible(false);
	marker_position = (checkin_data.length-1) - valx;
	markers[marker_position].setVisible(true);
	map.setCenter(markers[marker_position].getPosition());
}

function aftershock(data) {

	var mapOptions = {
		zoom: 12,
		center: centerpt,
		mapTypeId: google.maps.MapTypeId.ROADMAP
	};

	map = new google.maps.Map(document.getElementById("map_canvas"), mapOptions);

	for (var i=1; i<checkin_data.length; i++) {
		if (checkin_data[i-1]['location'] != checkin_data[i]['location']) {
			var tmp_a = checkin_data[i-1]['location'].split(",");
			var tmp_b = checkin_data[i]['location'].split(",");

			lines.push(new google.maps.Polyline({
				path: new Array(new google.maps.LatLng(tmp_a[0], tmp_a[1]), new google.maps.LatLng(tmp_b[0], tmp_b[1])),
				strokeColor: "#000000",
				strokeOpacity: 1.0,
				strokeWeight: 2
			}));
		}
	}

	for (var y in checkin_data) {
		var tmp = checkin_data[y]['location'].split(",");
		markers.push(new google.maps.Marker({
			position: new google.maps.LatLng(tmp[0], tmp[1]),
			map: map,
			visible: false
		}));

		infowindows.push(new google.maps.InfoWindow({
			content: "<p><strong>"+checkin_data[y]['description']+"</strong><br><em>"+checkin_data[y]['occurred']+"</em></p>",
			maxWidth: 200
		}));
	}

	for (var x in lines) {
		lines[x].setMap(map);
	}

	for (var key2 in markers) {
		createMarker(markers[key2], infowindows[key2], map);
	}

	if (checkin_data.length > 0) {
		var tmp = checkin_data[0]['location'].split(",");
		centerpt = new google.maps.LatLng(tmp[0], tmp[1]);
		map.setCenter(centerpt);
		markers[0].setVisible(true);
	}

	var sld_max = checkin_data.length-1

	$(document).ready(function() {
	  $("#slider").slider({ min: 0, max: sld_max, slide: setvalue, value: sld_max });
	});

	google.maps.event.addDomListener(document.getElementById("g_n"), "click", function(ev) {
		map.setCenter(markers[marker_position].getPosition());
		$("#slider").slider( "option", "value", (checkin_data.length-1) - marker_position );
	});

	google.maps.event.addDomListener(document.getElementById("g_l"), "click", function(ev) {
		map.setCenter(markers[marker_position].getPosition());
		$("#slider").slider( "option", "value", (checkin_data.length-1) - marker_position );
	});

	google.maps.event.addDomListener(document.getElementById("g_p"), "click", function(ev) {
		map.setCenter(markers[marker_position].getPosition());
		$("#slider").slider( "option", "value", (checkin_data.length-1) - marker_position );
	});

	google.maps.event.addDomListener(document.getElementById("g_e"), "click", function(ev) {
		map.setCenter(markers[marker_position].getPosition());
		$("#slider").slider( "option", "value", (checkin_data.length-1) - marker_position );
	});
}