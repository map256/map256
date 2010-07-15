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

function createMarker(marker, infowindow, map) {
	google.maps.event.addListener(marker, 'click', function() {
		infowindow.open(map, marker);
	})
}

function setvalue(event, ui) {
	var valx = $("#slider").slider( "option", "value" );
	$("#slidervalue").val(valx);
	markers[marker_position].setVisible(false);
	marker_position = (checkin_data.length-1) - valx;
	markers[marker_position].setVisible(true);
	map.setCenter(markers[marker_position].getPosition());
}

function aftershock(data) {
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
			content: "<h4>"+checkin_data[y]['description']+"</h4>",
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
	}

	var sld_max = checkin_data.length-1

	$(document).ready(function() {
	  $("#slider").slider({ min: 0, max: sld_max, slide: setvalue, value: sld_max });
	});

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

function initialize() {
	var mapOptions = {
		zoom: 12,
		center: centerpt,
		mapTypeId: google.maps.MapTypeId.ROADMAP
	};

	map = new google.maps.Map(document.getElementById("map_canvas"), mapOptions);

}

function initialize_front() {
	var mapOptions = {
		zoom: 4,
		center: centerpt,
		mapTypeId: google.maps.MapTypeId.ROADMAP
	};

	var map = new google.maps.Map(document.getElementById("map_canvas"), mapOptions);
	var blarg = new Array();

	for (key in frontpage_userlist) {
		var path = new Array();

		for (var item in frontpage_userlist[key]) {
			var foo = frontpage_userlist[key][item].split(",");
			path.push(new google.maps.LatLng(foo[0], foo[1]));
		}

		lines.push(new google.maps.Polyline({
			path: path,
			strokeColor: "#FF0000",
			strokeOpacity: 1.0,
			strokeWeight: 4,
			map: map
		}));
		
		var bar = frontpage_userlist[key][0].split(",");

		markers[key] = new google.maps.Marker({
			position: new google.maps.LatLng(bar[0], bar[1]),
			map: map,
			title: key
		});
		
		infowindows[key] = new google.maps.InfoWindow({
			content: "<h4><a href=\"/t/"+key+"\">"+key+"</a></h4>",
			maxWidth: 200
		});
	}

	for (var key2 in markers) {
		createMarker(markers[key2], infowindows[key2], map);
	}
}

/*
    http://www.JSON.org/json_parse.js
    2009-05-31

    Public Domain.

    NO WARRANTY EXPRESSED OR IMPLIED. USE AT YOUR OWN RISK.

*/

/*members "", "\"", "\/", "\\", at, b, call, charAt, f, fromCharCode,
    hasOwnProperty, message, n, name, push, r, t, text
*/

var json_parse = (function () {

// This is a function that can parse a JSON text, producing a JavaScript
// data structure. It is a simple, recursive descent parser. It does not use
// eval or regular expressions, so it can be used as a model for implementing
// a JSON parser in other languages.

// We are defining the function inside of another function to avoid creating
// global variables.

    var at,     // The index of the current character
        ch,     // The current character
        escapee = {
            '"':  '"',
            '\\': '\\',
            '/':  '/',
            b:    '\b',
            f:    '\f',
            n:    '\n',
            r:    '\r',
            t:    '\t'
        },
        text,

        error = function (m) {

// Call error when something is wrong.

            throw {
                name:    'SyntaxError',
                message: m,
                at:      at,
                text:    text
            };
        },

        next = function (c) {

// If a c parameter is provided, verify that it matches the current character.

            if (c && c !== ch) {
                error("Expected '" + c + "' instead of '" + ch + "'");
            }

// Get the next character. When there are no more characters,
// return the empty string.

            ch = text.charAt(at);
            at += 1;
            return ch;
        },

        number = function () {

// Parse a number value.

            var number,
                string = '';

            if (ch === '-') {
                string = '-';
                next('-');
            }
            while (ch >= '0' && ch <= '9') {
                string += ch;
                next();
            }
            if (ch === '.') {
                string += '.';
                while (next() && ch >= '0' && ch <= '9') {
                    string += ch;
                }
            }
            if (ch === 'e' || ch === 'E') {
                string += ch;
                next();
                if (ch === '-' || ch === '+') {
                    string += ch;
                    next();
                }
                while (ch >= '0' && ch <= '9') {
                    string += ch;
                    next();
                }
            }
            number = +string;
            if (isNaN(number)) {
                error("Bad number");
            } else {
                return number;
            }
        },

        string = function () {

// Parse a string value.

            var hex,
                i,
                string = '',
                uffff;

// When parsing for string values, we must look for " and \ characters.

            if (ch === '"') {
                while (next()) {
                    if (ch === '"') {
                        next();
                        return string;
                    } else if (ch === '\\') {
                        next();
                        if (ch === 'u') {
                            uffff = 0;
                            for (i = 0; i < 4; i += 1) {
                                hex = parseInt(next(), 16);
                                if (!isFinite(hex)) {
                                    break;
                                }
                                uffff = uffff * 16 + hex;
                            }
                            string += String.fromCharCode(uffff);
                        } else if (typeof escapee[ch] === 'string') {
                            string += escapee[ch];
                        } else {
                            break;
                        }
                    } else {
                        string += ch;
                    }
                }
            }
            error("Bad string");
        },

        white = function () {

// Skip whitespace.

            while (ch && ch <= ' ') {
                next();
            }
        },

        word = function () {

// true, false, or null.

            switch (ch) {
            case 't':
                next('t');
                next('r');
                next('u');
                next('e');
                return true;
            case 'f':
                next('f');
                next('a');
                next('l');
                next('s');
                next('e');
                return false;
            case 'n':
                next('n');
                next('u');
                next('l');
                next('l');
                return null;
            }
            error("Unexpected '" + ch + "'");
        },

        value,  // Place holder for the value function.

        array = function () {

// Parse an array value.

            var array = [];

            if (ch === '[') {
                next('[');
                white();
                if (ch === ']') {
                    next(']');
                    return array;   // empty array
                }
                while (ch) {
                    array.push(value());
                    white();
                    if (ch === ']') {
                        next(']');
                        return array;
                    }
                    next(',');
                    white();
                }
            }
            error("Bad array");
        },

        object = function () {

// Parse an object value.

            var key,
                object = {};

            if (ch === '{') {
                next('{');
                white();
                if (ch === '}') {
                    next('}');
                    return object;   // empty object
                }
                while (ch) {
                    key = string();
                    white();
                    next(':');
                    if (Object.hasOwnProperty.call(object, key)) {
                        error('Duplicate key "' + key + '"');
                    }
                    object[key] = value();
                    white();
                    if (ch === '}') {
                        next('}');
                        return object;
                    }
                    next(',');
                    white();
                }
            }
            error("Bad object");
        };

    value = function () {

// Parse a JSON value. It could be an object, an array, a string, a number,
// or a word.

        white();
        switch (ch) {
        case '{':
            return object();
        case '[':
            return array();
        case '"':
            return string();
        case '-':
            return number();
        default:
            return ch >= '0' && ch <= '9' ? number() : word();
        }
    };

// Return the json_parse function. It will have access to all of the above
// functions and variables.

    return function (source, reviver) {
        var result;

        text = source;
        at = 0;
        ch = ' ';
        result = value();
        white();
        if (ch) {
            error("Syntax error");
        }

// If there is a reviver function, we recursively walk the new structure,
// passing each name/value pair to the reviver function for possible
// transformation, starting with a temporary root object that holds the result
// in an empty key. If there is not a reviver function, we simply return the
// result.

        return typeof reviver === 'function' ? (function walk(holder, key) {
            var k, v, value = holder[key];
            if (value && typeof value === 'object') {
                for (k in value) {
                    if (Object.hasOwnProperty.call(value, k)) {
                        v = walk(value, k);
                        if (v !== undefined) {
                            value[k] = v;
                        } else {
                            delete value[k];
                        }
                    }
                }
            }
            return reviver.call(holder, key, value);
        }({'': result}, '')) : result;
    };
}());
