# -*- coding: utf-8 -*-

# Copyright 2007 - 2012 Harri Pitkänen (hatapitk@iki.fi)
# Program to generate lexicon files for Suomi-malaga Voikko edition

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import sys
sys.path.append("common")
import hfconv
import generate_lex_common
import voikkoutils
import xml.dom.minidom
import codecs
from string import rfind
from xml.dom import Node

flag_attributes = voikkoutils.readFlagAttributes(generate_lex_common.VOCABULARY_DATA + u"/flags.txt")

# Get command line options
OPTIONS = generate_lex_common.get_options()

# Inflection class map
CLASSMAP = hfconv.compileClassmapREs(hfconv.modern_classmap)

# No special vocabularies are built for Voikko
generate_lex_common.SPECIAL_VOCABULARY = []


main_vocabulary = codecs.open(OPTIONS["destdir"] + u"/" + "joukahainen.lexc", 'w', 'UTF-8')
main_vocabulary.write(u"! This is automatically generated intermediate lexicon file for\n")
main_vocabulary.write(u"! VVFST morphology. The original source data is\n")
main_vocabulary.write(u"! distributed under the GNU General Public License, version 2 or\n")
main_vocabulary.write(u"! later, as published by the Free Software Foundation. You should\n")
main_vocabulary.write(u"! have received the original data, tools and instructions to\n")
main_vocabulary.write(u"! generate this file (or instructions to obtain them) wherever\n")
main_vocabulary.write(u"! you got this file from.\n\n")

main_vocabulary.write(u"LEXICON Nimisana\n")


def frequency(word):
	fclass = word.getElementsByTagName("fclass")
	if len(fclass) == 0: return 7
	return int(generate_lex_common.tValue(fclass[0]))

# Check the style flags of the word according to current options.
# Returns True if the word is acceptable, otherwise returns false.
def check_style(word):
	global OPTIONS
	for styleE in word.getElementsByTagName("style"):
		for style in generate_lex_common.tValues(styleE, "flag"):
			if style == "foreignloan":
				continue
			if not style in OPTIONS["style"]: return False
	return True

# Returns True if the word is acceptable according to its usage flags.
def check_usage(word):
	global OPTIONS
	wordUsage = word.getElementsByTagName("usage")
	if len(wordUsage) == 0: return True
	for usageE in wordUsage:
		for usage in generate_lex_common.tValues(usageE, "flag"):
			if usage in OPTIONS["extra-usage"]: return True
	return False

# Returns VFST word class for given word in Joukahainen
def get_vfst_word_class(j_wordclasses):
	if "pnoun_place" in j_wordclasses: return u"[Lep]"
	if "pnoun_firstname" in j_wordclasses: return u"[Lee]"
	if "pnoun_lastname" in j_wordclasses: return u"[Les]"
	if "pnoun_misc" in j_wordclasses: return u"[Lem]"
	if "verb" in j_wordclasses: return u"[Lt]"
	if "adjective" in j_wordclasses and "noun" in j_wordclasses: return u"[Lnl]"
	if "adjective" in j_wordclasses: return u"[Ll]"
	if "noun" in j_wordclasses: return u"[Ln]"
	return None

# Returns a string describing the structure of a word, if necessary for the spellchecker
# or hyphenator
# TODO: strip extra characters at the end of pattern (as is done with Malaga)
def get_structure(wordform, vfst_word_class):
	needstructure = False
	ispropernoun = vfst_word_class[0:3] == u'[Le'
	structstr = u'[Xr]'
	for i in range(len(wordform)):
		c = wordform[i]
		if c == u'-':
			structstr = structstr + u"-="
			needstructure = True
		elif c == u'|': structstr = structstr
		elif c == u'=':
			structstr = structstr + u"="
			needstructure = True
		elif c == u':':
			structstr = structstr + u":"
			needstructure = True
		elif c.isupper():
			structstr = structstr + u"i"
			if not (ispropernoun and i == 0): needstructure = True
		else: structstr = structstr + u"p"
	if needstructure: return structstr + u'[X]'
	else: return u""

def get_diacritics(word):
	diacritics = []
	for group in word.childNodes:
		if group.nodeType != Node.ELEMENT_NODE:
			continue
		for flag in group.childNodes:
			if flag.nodeType != Node.ELEMENT_NODE:
				continue
			if flag.tagName != "flag":
				continue
			flagName = flag.firstChild.wholeText
			if flagName == u"ei_yks":
				diacritics.append(u"@P.EI_YKS@")
			elif flagName == u"ysj":
				diacritics.append(u"@R.YS_ALKANUT@")
	return diacritics

def handle_word(word):
	global OPTIONS
	global CLASSMAP
	# Drop words that are not needed in the Voikko lexicon
	if generate_lex_common.has_flag(word, "not_voikko"): return
	if not check_style(word): return
	if not check_usage(word): return
	if frequency(word) >= OPTIONS["frequency"] + 1: return
	if frequency(word) == OPTIONS["frequency"] and generate_lex_common.has_flag(word, "confusing"): return
	
	# Get the inflection class. Exactly one inflection class is needed
	voikko_infclass = None
	for infclass in word.getElementsByTagName("infclass"):
		if infclass.getAttribute("type") != "historical":
			voikko_infclass = generate_lex_common.tValue(infclass)
			break
	if voikko_infclass == None: return
	if voikko_infclass == u"poikkeava": return
	
	# Get the word classes
	wordclasses = generate_lex_common.tValues(word.getElementsByTagName("classes")[0], "wclass")
	vfst_word_class = get_vfst_word_class(wordclasses)
	if vfst_word_class == None: return
	
	# Get diacritics
	diacritics = reduce(lambda x, y: x + y, get_diacritics(word), u"")
	
	# Get forced vowel type
	forced_inflection_vtype = generate_lex_common.vowel_type(word.getElementsByTagName("inflection")[0])
	
	# Construct debug information
	debug_info = u""
	if OPTIONS["sourceid"]:
		debug_info = u', sourceid: "%s"' % word.getAttribute("id")
	
	# Process all alternative forms
	singlePartForms = []
	multiPartForms = []
	for altform in generate_lex_common.tValues(word.getElementsByTagName("forms")[0], "form"):
		wordform = altform.replace(u'|', u'').replace(u'=', u'')
		if len(altform) == len(wordform.replace(u'-', u'')):
			singlePartForms.append(altform)
		else:
			multiPartForms.append(altform)
		(alku, jatko) = generate_lex_common.get_malaga_inflection_class(wordform, voikko_infclass, wordclasses, CLASSMAP)
		if forced_inflection_vtype == voikkoutils.VOWEL_DEFAULT:
			vtype = voikkoutils.get_wordform_infl_vowel_type(altform)
		else: vtype = forced_inflection_vtype
		if vtype == voikkoutils.VOWEL_FRONT: vfst_vtype = u'ä'
		elif vtype == voikkoutils.VOWEL_BACK: vfst_vtype = u'a'
		elif vtype == voikkoutils.VOWEL_BOTH: vfst_vtype = u'aä'
		rakenne = get_structure(altform, vfst_word_class)
		if alku == None:
			errorstr = u"ERROR: Malaga class not found for (%s, %s)\n" \
				% (wordform, voikko_infclass)
			generate_lex_common.write_entry(main_vocabulary, {}, word, errorstr)
			sys.stderr.write(errorstr.encode(u"UTF-8"))
			sys.exit(1)
		if jatko not in [u"nainen", u"hattu"] or vfst_word_class not in [u"[Ln]", u"[Les]"]:
			continue
		#entry = u'[perusmuoto: "%s", alku: "%s", luokka: %s, jatko: <%s>, äs: %s%s%s%s];' \
		#          % (wordform, alku, malaga_word_class, jatko, malaga_vtype, malaga_flags,
		#	   generate_lex_common.get_structure(altform, malaga_word_class),
		#	   debug_info)
		alku = alku.lower()
		entry = u'%s[Xp]%s[X]%s%s%s:%s%s Nom%s_%s ;' \
		        % (vfst_word_class, wordform, get_structure(altform, vfst_word_class),
		        alku, diacritics, alku, diacritics, jatko.title(), vfst_vtype)
		main_vocabulary.write(entry + u"\n")
	
	# Sanity check for alternative forms: if there are both multi part forms and single part forms
	# then all multi part forms must end with a part contained in the single part set.
	if singlePartForms:
		for multiPartForm in multiPartForms:
			lastPart = multiPartForm[max(rfind(multiPartForm, u"="), rfind(multiPartForm, u"|"), rfind(multiPartForm, u"-")) + 1:]
			if lastPart not in singlePartForms:
				sys.stderr.write(u"ERROR: suspicious alternative spelling: %s\n" % multiPartForm)
				sys.exit(1)


voikkoutils.process_wordlist(generate_lex_common.VOCABULARY_DATA + u'/joukahainen.xml', \
                             handle_word, True)

main_vocabulary.close()
