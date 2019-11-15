from __future__ import print_function
from __future__ import absolute_import

__license__ = """

Copyright (c) 2012-2014, Uwe Schmitt, all rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

Neither the name of the ETH Zurich nor the names of its contributors may be
used to endorse or promote products derived from this software without specific
prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import os.path
import re
from collections import defaultdict
from autowrap.ConversionProvider import setup_converter_registry
from autowrap.DeclResolver import (ResolvedClass, ResolvedEnum, ResolvedTypeDef, ResolvedFunction)
from autowrap.code_generators.CodeGeneratorBase import CodeGeneratorBase
import autowrap.Code as Code
import logging as logger

IS_PY3 = True
try:
	unicode = unicode
except NameError:
	# 'unicode' is undefined, must be Python 3
	str = str
	unicode = str
	bytes = bytes
	basestring = (str, bytes)
else:
	IS_PY3 = False
	# 'unicode' exists, must be Python 2
	str = str
	unicode = unicode
	bytes = str
	basestring = basestring

class CLRGenerator(CodeGeneratorBase):
	def __init__(self, resolved, instance_mapping, pyx_target_path=None, manual_code=None, extra_cimports=None,
				 allDecl={}):
		if IS_PY3:
			super().__init__(resolved, instance_mapping, pyx_target_path, manual_code,
							 extra_cimports, allDecl)
		else:
			super(CodeGeneratorBase, self).__init__(resolved, instance_mapping, pyx_target_path, manual_code,
													extra_cimports, allDecl)

	def create_code_file(self, debug=False):
		self.setup_cimport_paths()
		self.create_cimports()
		self.create_foreign_cimports()
		self.create_includes()

		def create_for(clz, method):
			for resolved in self.resolved:
				if resolved.wrap_ignore:
					continue
				if isinstance(resolved, clz):
					method(resolved)

		# first wrap classes, so that self.class_codes[..] is initialized
		# for attaching enums or static functions
		create_for(ResolvedClass, self.create_wrapper_for_class)
		create_for(ResolvedEnum, self.create_wrapper_for_enum)
		create_for(ResolvedFunction, self.create_wrapper_for_free_function)

		# resolve extra
		for clz, codes in self.class_codes_extra.items():
			if clz not in self.class_codes:
				raise Exception("Cannot attach to class", clz, "make sure all wrap-attach are in the same file as parent class")
			for c in codes:
				self.class_codes[clz].add(c)

		# Create code for the pyx file
		if self.write_pxd:
			pyx_code = self.create_default_cimports().render()
			pyx_code += "\n".join(ci.render() for ci in self.top_level_pyx_code)
		else:
			pyx_code = "\n".join(ci.render() for ci in self.top_level_code)
			pyx_code += "\n".join(ci.render() for ci in self.top_level_pyx_code)

		pyx_code += " \n"
		names = set()
		for n, c in self.class_codes.items():
			pyx_code += c.render()
			pyx_code += "\n};"
			names.add(n)

		# manual code which does not extend wrapped classes:
		for name, c in self.manual_code.items():
			if name not in names:
				pyx_code += c.render()
			pyx_code += "\n};"

		# Create code for the pxd file
		pxd_code = "\n".join(ci.render() for ci in self.top_level_code)
		pxd_code += "\n};"
		for n, c in self.class_pxd_codes.items():
			pxd_code += c.render()
			pxd_code += "\n};"

		if debug:
			print(pxd_code)
			print(pyx_code)
		with open(self.target_path, "w") as fp:
			fp.write(pyx_code)

		if self.write_pxd:
			with open(self.target_pxd_path, "w") as fp:
				fp.write(pxd_code)


	def create_wrapper_for_enum(self, decl):
		"""
		Creates a c++/CLI enum from an enum decl
		:param decl: the enumeration declaration
		:return: None
		"""
		self.wrapped_enums_cnt += 1
		if decl.cpp_decl.annotations.get("wrap-attach"):
			name = "__" + decl.name
		else:
			name = decl.name
			logger.info("create wrapper for enum %s" % name)

		enum_code = Code.Code()
		enumerated = [
			" {name} = {value} ".format(name=n, value=v) for n, v in decl.items
		]
		enum_code.add("""
                   |
                   |enum class $name {\n\t$content\n};
                 """, name=name, content=",\n\t".join([c.strip() for c in enumerated]))

		self.class_codes[decl.name] = enum_code
		for class_name in decl.cpp_decl.annotations.get("wrap-attach", []):
			code = Code.Code()
			display_name = decl.cpp_decl.annotations.get("wrap-as", [decl.name])[0]
			code.add("%s = %s" % (display_name, "__" + decl.name))
			self.class_codes[class_name].add(code)


	def create_wrapper_for_class(self, r_class):
		self.wrapped_classes_cnt += 1
		self.wrapped_methods_cnt += len(r_class.methods)
		cname = r_class.name
		if r_class.cpp_decl.annotations.get("wrap-attach"):
			pyname = "__" + r_class.name
		else:
			pyname = cname

		logger.info("create wrapper for class %s" % cname)
		cy_type = self.cr.cython_type(cname)
		class_pxd_code = Code.Code()
		class_code = Code.Code()

		# Class documentation (multi-line)
		docstring = "/// <summary>\n\t///\tC++/CLI implementation of %s\n" % cy_type
		if r_class.cpp_decl.annotations.get("wrap-inherits", "") != "":
			docstring += "\t///\tInherits from %s\n" % r_class.cpp_decl.annotations.get("wrap-inherits", "")

		extra_doc = r_class.cpp_decl.annotations.get("wrap-doc", "")
		for extra_doc_line in extra_doc:
			docstring += "\n\t///\t" + extra_doc_line
		docstring += "\t/// </summary>" if docstring.endswith("\n") else "\n\t///</summary>"

		if r_class.methods:
			shared_ptr_inst = "%s^ inst" % cy_type
			if len(r_class.wrap_manual_memory) != 0 and r_class.wrap_manual_memory[0] != "__old-model":
				shared_ptr_inst = r_class.wrap_manual_memory[0]
			if self.write_pxd:
				class_pxd_code.add("""
								|
								|public ref class $pyname 
								|{
								|    $docstring
								|
								|    $shared_ptr_inst
								|
								""", locals())
				shared_ptr_inst = "// see .pxd file for cdef of inst ptr" # do not implement in pyx file, only in pxd file

			if len(r_class.wrap_manual_memory) != 0:
				class_code.add("""
                                |
                                |public ref class $pyname
                                |{
                                |    $docstring
                                |
                                """, locals())
			else:
				class_code.add("""
|
|public ref class $pyname
|{
|    $docstring
|public:
|	$pyname() {
|		isDisposed = false;
|	}
|	~$pyname() {
|		if (_isDisposed) { return; }
|		this->!$pyname();
|		_isDisposed = true;
|	}
|
|	$shared_ptr_inst
|
|protected:
|	!$pyname();
|
|private:
|	bool _isDisposed;
|
""", 
							   locals())
		else:
			# Deal with pure structs (no methods)
			class_pxd_code.add("""
                            |
                            |value struct $pyname
                            |{
                            |    $docstring
                            |
    						|
                            |
                            """, locals())

		if len(r_class.wrap_hash) != 0:
			class_code.add("""
						|
						|    GetHashCode() {
						|    	return hash(%(this.inst).{});
						|	}
						""".format(r_class.wrap_hash[0]), locals())
		
		self.class_pxd_codes[cname] = class_pxd_code
		self.class_codes[cname] = class_code

		cons_created = False

		for attribute in r_class.attributes:
			if not attribute.wrap_ignore:
				class_code.add(self._create_wrapper_for_attribute(attribute))

		iterators, non_iter_methods = self.filterout_iterators(r_class.methods)

		for (name, methods) in non_iter_methods.items():
			if name == r_class.name:
				codes = self.create_wrapper_for_constructor(r_class, methods)
				cons_created = True
			else:
				codes = self.create_wrapper_for_method(r_class, name, methods)

			for ci in codes:
				class_code.add(ci)

		has_ops = dict()
		for ops in ["==", "!=", "<", "<=", ">", ">="]:
			has_op = ("operator%s" % ops) in non_iter_methods
			has_ops[ops] = has_op

		if any(v for v in has_ops.values()):
			code = self.create_special_cmp_method(r_class, has_ops)
			class_code.add(code)

		codes = self._create_iter_methods(iterators, r_class.instance_map, r_class.local_map)
		for ci in codes:
			class_code.add(ci)

		extra_methods_code = self.manual_code.get(cname)
		if extra_methods_code:
			class_code.add(extra_methods_code)

		class_pxd_code.add("\n};")

		for class_name in r_class.cpp_decl.annotations.get("wrap-attach", []):
			code = Code.Code()
			display_name = r_class.cpp_decl.annotations.get("wrap-as", [r_class.name])[0]
			code.add("%s = %s;" % (display_name, "__" + r_class.name))
			tmp = self.class_codes_extra.get(class_name, [])
			tmp.append(code)
			self.class_codes_extra[class_name] = tmp


	def _create_iter_methods(self, iterators, instance_mapping, local_mapping):
		return []

	def _create_overloaded_method_decl(self, py_name, dispatched_m_names, methods, use_return, use_kwargs=False):
		pass

	def create_wrapper_for_method(self, cdcl, py_name, methods):
		return []

	def _create_fun_decl_and_input_conversion(self, code, py_name, method, is_free_fun=False):
		pass

	def _create_wrapper_for_attribute(self, attribute):
		pass

	def create_wrapper_for_nonoverloaded_method(self, cdcl, py_name, method):
		pass

	def create_wrapper_for_free_function(self, decl):
		pass

	def _create_wrapper_for_free_function(self, decl, name=None, orig_cpp_name=None):
		pass

	def create_wrapper_for_constructor(self, class_decl, constructors):
		return []

	def create_wrapper_for_nonoverloaded_constructor(self, class_decl, py_name, cons_decl):
		pass

	def create_special_mul_method(self, cdcl, mdcl):
		pass

	def create_special_add_method(self, cdcl, mdcl):
		pass

	def create_special_iadd_method(self, cdcl, mdcl):
		pass

	def create_special_getitem_method(self, mdcl):
		pass

	def create_cast_methods(self, mdecls):
		pass

	def create_special_cmp_method(self, cdcl, ops):
		pass

	def create_special_copy_method(self, class_decl):
		pass

	def create_foreign_cimports(self):
		pass

	def create_cimports(self):
		pass

	def create_default_cimports(self):
		pass

	def create_std_cimports(self):
		pass

	def create_includes(self):
		pass
