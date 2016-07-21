from django.shortcuts import render
from django.http import JsonResponse, HttpResponseRedirect
from .models import Bike, Component
from ..component_factors.models import CategoryOption, ItemOption
from ..bike_factors.models import BikeOption, BrandOption, CosmeticOption, FeaturesOption, FrameOption
import requests
import json
import string
import random
from .api import LightspeedApi
from .forms import BikeForm, componentForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
# from django.views.generic.base import TemplateView



# Create your views here.
@login_required()
def home(request):
	oAuth = {
		'clientKey': 'gkbScrumTesting', 
		'clientSecret': '$2y$10$m4XAnnZtm/N0IC/pz9wfz.WJ24EsPoQOygqYWOBsk/T3CpQvPiCYu'
	}
	# auth = ('abarlow85@gmail.com', 'gkbScrum')
	url = 'https://cloud.merchantos.com/oauth/authorize.php?response_type=code&client_id=' + oAuth['clientKey'] + '&scope=employee:all'
	response = requests.get(url, auth=auth)
	print 'this is our response'
	print dir(response)
	print response.headers	
	if request.user.is_superuser:
		logout(request)
		return HttpResponseRedirect('/login')
	return render(request, 'bike_donations/index.html')

@login_required()
def form_data(request):
	context = {
		'bikeType' : serialize_selections(BikeOption.objects.all()),
		'brand' : serialize_selections(BrandOption.objects.all()),
		'cosmetic' : serialize_selections(CosmeticOption.objects.all()),
		'frame' : serialize_selections(FrameOption.objects.all()),
		'features' : serialize_selections(FeaturesOption.objects.all())
	}
	return JsonResponse(context)


def serialize_selections(query_set):
	data = {}

	for obj in query_set:
		if type(obj) == BikeOption:
			data[obj.option] = {'status' : False, 'price_factor' : obj.price_factor}
		else:
			requisites = []
			for req in obj.requisites.values():
				requisites.append(req['option'])


			data[obj.option] = {'status' : False, 'price_factor' : obj.price_factor, 'requisites':requisites}

	return data

@login_required()
def donateBike_post(request):
	print("user", request.user.username)
	username = request.user.username
	parsed_json = json.loads(request.body)
	optionsArray = []

	bikeoption = BikeOption.objects.get(option=parsed_json["bikeType"])
	optionsArray.append(bikeoption)

	if 'brand' in parsed_json:
		brandoption = BrandOption.objects.get(option=parsed_json["brand"])
		optionsArray.append(brandoption)
		parsed_json["brand"]=brandoption.id
		request.session['brand'] = brandoption.option
	else:
		parsed_json['brand'] = None
		request.session['brand'] = ""

	cosmeticoption = CosmeticOption.objects.get(option=parsed_json["cosmetic"])
	optionsArray.append(cosmeticoption)


	featuresoption = [FeaturesOption.objects.get(option=feature) for feature in parsed_json["features"]]

	if 'frame' in parsed_json:
		frameoption = FrameOption.objects.get(option=parsed_json["frame"])
		optionsArray.append(frameoption)
		parsed_json["frame"]=frameoption.id

	else:
		parsed_json['frame'] = None

	if "quantity" in parsed_json:
		parsed_json["quantity"] = int(parsed_json["quantity"])
		quantity = parsed_json["quantity"]
	else:
		quantity = 1

	parsed_json["features"]=[obj.id for obj in featuresoption]
	parsed_json["cosmetic"]=cosmeticoption.id
	parsed_json["bikeType"] = bikeoption.id

	form = BikeForm(parsed_json)

	if form.is_valid():
		price = getBikePrice(optionsArray, featuresoption)
		if float(price) > 100.00:
			parsed_json["djangoPrice"] = price
		else:
			parsed_json["djangoPrice"] = "Program"


	else:
		print ("Not valid", form.errors.as_json())
	descriptionString = str(bikeoption.option + " " + request.session['brand'] + " " + cosmeticoption.option)
	bikePrice = parsed_json['djangoPrice']
	lightspeed = LightspeedApi()

	#let's not return pythonDictionary, instead let's return
	# finalResult = {'success': response.reason, 'bikeAdded': pythonDictionary}
	newBicycle = lightspeed.create_item(descriptionString, bikePrice, username, quantity)

	if newBicycle['status'] == 200:

	# session for label template
		request.session['customSku'] = newBicycle['bikeAdded']['customSku']

		request.session['type'] = bikeoption.option
		request.session['price'] = bikePrice
		return JsonResponse({'success' : True})
	else:
		return JsonResponse({'success' : False, 'error' : newBicycle['status']})

@login_required()
def component_post(request):
	parsed_json = json.loads(request.body)

	categorySelect = CategoryOption.objects.get(option=parsed_json['category'])
	itemSelect = ItemOption.objects.get(option=parsed_json['item'])
	descriptionString = parsed_json['item'] + " " + parsed_json['category']
	itemType = parsed_json['category']

	parsed_json['item'] = itemSelect.id
	parsed_json['category'] = categorySelect.id
	quantity = 1
	if "quantity" in parsed_json:
		parsed_json["quantity"] = int(parsed_json["quantity"])
		quantity = parsed_json["quantity"]
	

	form = componentForm(parsed_json)

	if form.is_valid():
		lightspeed = LightspeedApi()
		newComponent = lightspeed.create_item(descriptionString, int(parsed_json['price']), request.user.username, quantity)

		if newComponent['status'] == 200:
			request.session['customSku'] = newComponent['bikeAdded']['customSku']
			request.session['price'] = parsed_json['price']
			request.session['type'] = None
			request.session['brand'] = itemSelect.option
			return JsonResponse({'status' : True})
		else:
			return JsonResponse({'status' : False, 'error' : newComponent['status']})

	else:
		print ("Not valid", form.errors.as_json())
		return JsonResponse(form.errors.as_json(), safe=False)


def getBikePrice(optionsArray, featuresoption):
	basePrice = 200.00
	price_factor = 1
	nego_factor = 1.05
	for option in optionsArray:
		price_factor *= option.price_factor
	for feature in featuresoption:
		price_factor *= feature.price_factor
	return format(basePrice * float(price_factor) * nego_factor, '.2f')

@login_required()
def print_label(request):
	label = {
		'customSku' : request.session['customSku'],
		'brand' : request.session['brand']
		
	}

	if request.session['price'] == "Program":
		label['Program'] = True
	else: 
		label['price'] = request.session['price']

	if request.session['type'] is not None:
		label['type'] = request.session['type']

	return render(request, 'bike_donations/barcode.html', label)

@login_required()
def component_data(request):
	components = serialize_componentFactor(ItemOption.objects.all())
	return JsonResponse(components)

def serialize_componentFactor(query_set):
	comp = {}
	for obj in query_set:
		category = str(obj.requisites)
		if  category in comp:
	
			comp[category].append({"item":obj.option,"price":obj.price})
		else:
			comp[category] = [{"item":obj.option,"price":obj.price}]
		
	return comp

@login_required()
def loggingout(request):
	logout(request)
	return HttpResponseRedirect('/login')

