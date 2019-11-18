from autowrap.Code import Code
import logging as logger

class WrapperBase():
	def __init__(self, decl):
		self.decl = decl
	
	def render(self):
		"""renders the c++/cli wrapper code and returns it as a code tuple (header, impl.)"""
		return self.render_header(), self.render_implmentation()
	
	def render_header(self):
		"""render the header code for this wrapper"""
		raise NotImplementedError

	def render_implmentation(self):
		"""Create and return code for the implementation"""
		raise NotImplementedError


class ClassWrapper(WrapperBase):
	def __init__(self, decl):
		super().__init__(decl)
		self.header, self.implmentation = self.render()

	def render_header(self):
		"""render the header code for this wrapper"""
		return self._render_header() if self.header is None else self.header

	def render_implmentation(self):
		"""Create and return code for the implementation"""
		return self._render_impl() if self.implmentation \
									  is None else self.implmentation

	def _render_header(self):
		return Code()

	def _render_impl(self):
		return Code()


def MethodWrapper(decl, m_return_type, marshaller_name):
	"""
	Creates a method wrapper from its cython declaration
	:param: decl -> the cpp_decl
	:param: m_return_type -> the managed return type
	:param: marshaller_name -> the marshaller function to convert the native return type to the m_return_type 
	"""
	code, name = Code(), decl.cpp_decl.name
	# create signature
	args = ",".join([
		("{t} {n}".format(t=t, n=n)
		 	if (n and n != "self") else "in_%d" % i) \
				for i, (n, t) in enumerate(decl.arguments)
	])
	sig = "{m_return_type} {name}(params)".format(m_return_type=m_return_type, name=name, params="")
	body = "this->{name}(args);".format(**locals())
	if decl.return_type != "void":
		body = "{rtype} rt = ".format(rtype=decl.return_type) + body
		body += "return {marshaller}(rt);".format(marshaller=marshaller_name)
	code.add("$sig { $body }", locals())
	return sig+";\n", code


# Functional component => returns render tuple
def EnumWrapper(decl):
	"""
		Creates a c++/CLI enum from an enum decl
		:param decl: the enumeration declaration
		:return: the enum code
		"""
	if decl.cpp_decl.annotations.get("wrap-attach"):
		name = "__" + decl.name # indicates attached elsewhere
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
	enum_code_copy = Code()
	enum_code_copy.add(enum_code.render())
	return enum_code, enum_code_copy


